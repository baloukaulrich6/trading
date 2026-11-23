import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from horaires_nkap import fenetre_entree, prochain_reveil


def test_horaire_douala_et_minuit(monkeypatch):
    monkeypatch.delenv("HEURE_EXECUTION", raising=False)
    monkeypatch.delenv("HEURE_LIMITE", raising=False)
    assert not fenetre_entree(datetime(2026, 11, 23, 7, 59, tzinfo=UTC))
    assert fenetre_entree(datetime(2026, 11, 23, 8, 0, tzinfo=UTC))
    assert fenetre_entree(datetime(2026, 11, 23, 22, 59, tzinfo=UTC))
    assert not fenetre_entree(datetime(2026, 11, 23, 23, 0, tzinfo=UTC))
    assert not fenetre_entree(datetime(2026, 11, 28, 10, 0, tzinfo=UTC))
    assert prochain_reveil(datetime(2026, 11, 28, 10, 0, tzinfo=UTC)) == "2026-11-30T09:00:00+01:00"


def test_ancienne_fenetre_et_horaire_inverse(monkeypatch):
    monkeypatch.setenv("HEURE_EXECUTION", "09:15")
    monkeypatch.setenv("HEURE_LIMITE", "21:00")
    assert fenetre_entree(datetime(2026, 11, 23, 19, 59, tzinfo=UTC))
    assert not fenetre_entree(datetime(2026, 11, 23, 20, 0, tzinfo=UTC))
    monkeypatch.setenv("HEURE_LIMITE", "08:00")
    with pytest.raises(ValueError, match="minuit"):
        fenetre_entree(datetime(2026, 11, 23, 20, 0, tzinfo=UTC))
