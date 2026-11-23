import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from objectif_hfm import Objectif, SuiviObjectif


def test_objectif_en_usc_et_persistant(tmp_path):
    fichier = tmp_path / "automatique.db"
    objectif = Objectif(10, date(2026, 11, 27))
    instant = datetime(2026, 11, 27, 22, 59, tzinfo=UTC)
    suivi = SuiviObjectif(fichier, objectif)
    en_cours = suivi.observer("hfm:1", 501, "USC", instant)
    assert en_cours["solde_usd"] == pytest.approx(5.01)
    assert not en_cours["bloque"]
    assert suivi.observer("hfm:1", 1001, "USC", instant)["bloque"]
    assert SuiviObjectif(fichier, objectif).observer("hfm:1", 990, "USC", instant)["bloque"]
    assert not suivi.observer("hfm:2", 990, "USC", instant)["bloque"]


def test_echeance_douala_et_devise_inconnue(tmp_path):
    suivi = SuiviObjectif(tmp_path / "automatique.db", Objectif(10, date(2026, 11, 27)))
    instant = datetime(2026, 11, 27, 22, 59, tzinfo=UTC)
    assert suivi.observer("hfm:1", 8, "EUR", instant)["bloque"]
    expire = suivi.observer("hfm:1", 8, "USD", instant.replace(hour=23, minute=0))
    assert "Échéance" in expire["motif"] and expire["bloque"]
