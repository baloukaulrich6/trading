from pathlib import Path

import numpy as np
import pandas as pd

from nkap.backtest.moteur import Couts
from nkap.backtest.smc_rapport import ecrire_html, evaluer_cinq_ans
from nkap.configuration import charger_config


def test_cinq_ans_et_rapport_sans_ouvrir_reserve(tmp_path):
    _, p, limites = charger_config(Path("config"))
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B", tz="UTC")
    x = 100 + np.sin(np.arange(len(dates)) / 6)
    data = pd.DataFrame({"open": x, "high": x + .02, "low": x - .02, "close": x}, index=dates)
    couts = Couts(.001, .001, .01, 0, 1, .01, .01)
    rapport, simulation = evaluer_cinq_ans("EURUSD", data, p, limites, couts, 100,
                                         pd.Timestamp("2025-01-01", tz="UTC"))
    assert rapport["hors_echantillon"]["debut"].startswith("2023-01-01")
    assert not rapport["admission_reel"] and "reserve" not in rapport
    assert simulation.courbe
    fichier = tmp_path / "rapport.html"
    ecrire_html(fichier, rapport, simulation)
    assert "Courbe d’équité" in fichier.read_text(encoding="utf-8")
