from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nkap.backtest.metriques import mesurer, monte_carlo
from nkap.backtest.moteur import Couts, simuler
from nkap.backtest.walk_forward import verifier_reserve, walk_forward
from nkap.configuration import Parametres, charger_config


def test_signal_cloture_ordre_ouverture_et_gap():
    _, parametres, limites = charger_config(Path("config"))
    p = Parametres.model_validate({**parametres.model_dump(), "regime": "er", "entree_turtles": 2,
                                   "periode_er": 2, "periode_atr": 2, "stop_atr": 1})
    dates = pd.date_range("2025-01-01", periods=5, tz="UTC")
    data = pd.DataFrame({"open": [10, 11, 12, 15, 8], "high": [11, 12, 13, 16, 9],
                         "low": [10, 11, 12, 15, 7], "close": [10.5, 11.5, 12.5, 15.5, 8]}, index=dates)
    couts = Couts(0.1, 0.05, 0.1, 0.1, 1, 0.01, 0.01, 0.2)
    resultat = simuler("EURUSD", data, p, limites, couts, dates[0], dates[-1] + pd.Timedelta(days=1), 1000)
    trade, = resultat.trades
    assert trade.signal.date == dates[2]
    assert trade.date_entree == dates[3]
    assert trade.date_sortie == dates[4]
    assert trade.motif == "stop" and trade.resultat_r < -1
    assert mesurer(resultat).profit_usd == pytest.approx(trade.resultat_usd - 0.2)
    assert monte_carlo(resultat) == monte_carlo(resultat)


def test_reserve_intacte_et_resultat_non_significatif():
    _, p, limites = charger_config(Path("config"))
    dates = pd.date_range("2017-01-01", "2025-12-31", freq="B", tz="UTC")
    x = 100 + 0.4 * np.sin(np.arange(len(dates)) / 10)
    data = pd.DataFrame({"open": x, "high": x + 0.01, "low": x - 0.01, "close": x}, index=dates)
    couts = Couts(0.02, 0.01, 0, 0.02, 1, 1, 1)
    rapport = walk_forward("EURUSD", data, p, limites, couts, 1)
    reserve = pd.Timestamp(rapport.reserve_debut)
    data.loc[data.index >= reserve] *= 50
    assert walk_forward("EURUSD", data, p, limites, couts, 1) == rapport
    assert len(rapport.fenetres) >= 3
    assert "Moins de 100 trades hors échantillon" in rapport.refus
    with pytest.raises(ValueError, match="Conserve la réserve intacte"):
        verifier_reserve("EURUSD", data, p, limites, couts, 1, rapport)
