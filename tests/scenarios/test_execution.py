from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from nkap.agents.gardien import proposer_stop
from nkap.configuration import Local
from nkap.domaine.modeles import Ordre, Signal
from nkap.execution.ordres import Compte, Executeur, Reponse, Validation


@pytest.fixture
def ordre():
    signal = Signal("EURUSD", datetime(2025, 5, 1, tzinfo=UTC), "achat", "TUR", 1)
    return Ordre("identifiant-1", signal, .01, 12, 11)


def test_modes_stop_et_dedoublonnage(ordre, tmp_path):
    mt5 = Mock()
    mt5.compte.return_value = Compte("123", True)
    mt5.disponible.return_value = True
    mt5.envoyer.return_value = Reponse("execute", "OK", "42")
    executeur = Executeur(tmp_path / "envois.db", mt5)
    demo = Local(mode="DEMO")
    validation = Validation()
    for mode, demande, compte in (
        (Local(), ordre, "123"), (Local(mode="REEL"), ordre, "123"),
        (demo, replace(ordre, stop=0), "123"), (demo, replace(ordre, stop=13), "123"),
        (demo, ordre, "autre"),
    ):
        assert executeur.executer(demande, compte, mode, validation).etat == "refuse"
    mt5.envoyer.assert_not_called()
    assert executeur.executer(ordre, "123", demo, validation).ticket == "42"
    executeur = Executeur(tmp_path / "envois.db", mt5)
    assert executeur.executer(ordre, "123", demo, validation).etat == "refuse"
    mt5.envoyer.assert_called_once()


def test_envoi_incertain_et_rapprochement(ordre, tmp_path):
    mt5 = Mock()
    mt5.compte.return_value = Compte("123", False)
    mt5.disponible.return_value = True
    mt5.envoyer.side_effect = TimeoutError
    executeur = Executeur(tmp_path / "envois.db", mt5)
    reel = Local(mode="REEL", confirmation_reelle=True)
    complet = Validation(True, True, 7, True)
    assert executeur.executer(ordre, "123", reel, Validation()).etat == "refuse"
    assert executeur.executer(ordre, "123", reel, complet).etat == "incertain"
    assert executeur.executer(replace(ordre, identifiant="id-2"), "123", reel, complet).etat == "refuse"
    mt5.rechercher.return_value = Reponse("incertain", "En attente")
    assert not executeur.reconcilier("123")
    mt5.rechercher.return_value = Reponse("execute", "Confirmé", "42")
    assert executeur.reconcilier("123")
    assert executeur.executer(ordre, "123", reel, complet).etat == "refuse"
    mt5.envoyer.assert_called_once()


def test_gardien_ne_recule_pas_le_stop():
    assert proposer_stop("achat", 10, 11, 1, 9) == 10
    assert proposer_stop("achat", 10, 12, 1, 10.5) == 11
    assert proposer_stop("achat", 10, 11.5, 1, 11) is None
    assert proposer_stop("vente", 10, 8, 1, 10) == 9
