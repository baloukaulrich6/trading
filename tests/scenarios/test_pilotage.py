import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pilotage_local import Pilotage


def test_pilotage_et_verrou_reel(monkeypatch):
    monkeypatch.setenv("HFM_DEMO_LOGIN", "123")
    monkeypatch.setenv("HFM_DEMO_SERVEUR", "HFM-Demo")
    p = Pilotage()
    assert p.etat()["applique"] == "TEST"
    assert p.demander("REEL")[0] == 409
    assert p.demander("DEMO")[0] == 200
    assert p.reveil.is_set() and p.etat()["applique"] == "TEST"
    assert p.appliquer() == "DEMO"
    assert not p.reveil.is_set() and p.demo["demo_uniquement"]
    assert p.demander("TEST")[0] == 200
    assert p.appliquer() == "TEST"
