from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nkap.adaptation.versions import Fantome, Versions, proposer
from nkap.backtest.metriques import Mesures
from nkap.backtest.walk_forward import Evaluation, Fenetre
from nkap.configuration import charger_config


def test_challenger_et_promotion_reversible(tmp_path):
    _, champion, _ = charger_config(Path("config"))
    with pytest.raises(ValueError, match="hors"):
        proposer(champion, "hors-borne", {"stop_atr": 0.1})
    p = proposer(champion, "er-1", {"regime": "er", "seuil_er": 0.4})
    ancien = Mesures(100, .12, .12, 1, 1.4, 110, 0)
    nouveau = replace(ancien, calmar=1.2, drawdown=.10)
    fenetres = tuple(Fenetre(f"{an}-01-01", f"{an + 1}-01-01", p.version, nouveau)
                     for an in range(2021, 2024))
    evaluation = Evaluation(fenetres, nouveau, None, (), "", "")
    jour = datetime(2025, 3, 1, tzinfo=UTC)
    fantome = Fantome(jour, jour + timedelta(days=28), True, nouveau)
    v = Versions(tmp_path / "versions.db", champion)
    assert not v.promouvoir(p, ancien, replace(evaluation, fenetres=()), fantome,
                            operateur="test", date=jour, confirme=True)
    assert not v.promouvoir(p, ancien, evaluation, fantome, operateur="test", date=jour, confirme=False)
    assert not v.promouvoir(p, ancien, evaluation, replace(fantome, sans_ordres=False),
                            operateur="test", date=jour, confirme=True)
    assert v.promouvoir(p, ancien, evaluation, fantome, operateur="test", date=jour, confirme=True)
    assert v.courant() == (p, 1)
    assert v.retrograder(drawdown_reel=.16, drawdown_teste=.1, facteur_profit_30=1, trades=4)
    assert v.courant() == (champion, .5)
