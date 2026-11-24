from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from nkap.agents.chef_orchestre import evaluer
from nkap.agents.eclaireur import Observation
from nkap.agents.filtre import filtrer
from nkap.agents.meteo import Meteo, observer
from nkap.agents.tresorier import Taille
from nkap.configuration import charger_config
from nkap.domaine.modeles import Decision, Position, Signal
from nkap.risque.limites import EtatRisque, autoriser
from nkap.stockage.greffier import Greffier


@pytest.fixture
def observation():
    signal = Signal("EURUSD", datetime(2025, 1, 1, tzinfo=UTC), "achat", "TUR", 0.01)
    return Observation(signal, 1, 0.03, 1, 0.2, True, (1.0,) * 100)


@pytest.mark.parametrize(("champs", "raison"), [
    ({"atr": 0}, "invalides"), ({"spread": 0.11}, "Spread"), ({"amplitude": 3.1}, "choc"),
    ({"retard_prix": 1.01}, "dépassée"), ({"marche_ouvert": False}, "fermé"),
])
def test_filtre(observation, champs, raison):
    decision = filtrer(replace(observation, **champs), Meteo(False, ""), en_pause=False, pari_risque=False)
    assert not decision.autorisee and raison in decision.raison


def test_limites_risque():
    _, _, limites = charger_config(Path("config"))
    etat = EtatRisque(1000, 1000, 1000, 0)
    position = Position("EURUSD", "achat", 10, (("USD", "vente"),))
    assert autoriser(etat, 10, (), limites).autorisee
    for etat_refuse, risque, expositions in [
        (replace(etat, capital=0), 1, ()),
        (replace(etat, sommet=1300), 1, ()),
        (replace(etat, capital_debut_jour=1040), 1, ()),
        (replace(etat, pertes_consecutives=5), 1, ()),
        (replace(etat, pertes_consecutives=2), 6, ()),
        (replace(etat, positions=(position,) * 4), 1, ()),
        (replace(etat, positions=(replace(position, risque=39),)), 2, ()),
        (replace(etat, positions=(replace(position, risque=-1),)), 2, ()),
        (replace(etat, positions=(position,) * 2), 1, (("USD", "vente"),)),
    ]:
        assert not autoriser(etat_refuse, risque, expositions, limites).autorisee


def test_relais_et_journal(observation, tmp_path):
    _, _, limites = charger_config(Path("config"))
    journal = Greffier(tmp_path / "traces.db")
    etat = EtatRisque(1000, 1000, 1000, 0)
    veto = Mock(return_value=Decision(True, "Vérifié"))
    args = (Meteo(False, ""), etat, Taille(1.2, 10, .01, .01, (("USD", "vente"),)),
            limites, journal, lambda: observation.signal.date, veto)
    assert evaluer(replace(observation, spread=5), *args, pari_risque=False, compte="demo") is None
    veto.assert_not_called()
    ordre = evaluer(observation, *args, pari_risque=False, compte="demo")
    assert ordre is not None and ordre.stop == pytest.approx(1.19)
    veto.side_effect = OSError("API en panne")
    assert evaluer(observation, *args, pari_risque=False, compte="demo") is None
    sortie = tmp_path / "journal.csv"
    journal.exporter(sortie)
    assert "Veto indisponible" in sortie.read_text()
    assert observer(-1, 1, 1, -1, 1).peur
