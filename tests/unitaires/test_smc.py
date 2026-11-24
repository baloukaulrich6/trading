from pathlib import Path

import pandas as pd

from nkap.configuration import charger_config
from nkap.strategies.smc import SMC, ReglagesSMC


def donnees():
    valeurs = [
        (10, 11, 9, 10), (11, 13, 10, 12), (10, 12, 8, 9),
        (10, 12, 9, 10), (14, 16, 14, 15), (14, 15, 12, 13),
        (11, 12, 6, 7), (7, 9, 6, 8),
    ]
    return pd.DataFrame(valeurs, columns=["open", "high", "low", "close"],
                        index=pd.date_range("2026-01-01", periods=len(valeurs), tz="UTC"))


def test_structure_et_score_sans_anticipation():
    _, p, _ = charger_config(Path("config"))
    s = SMC(ReglagesSMC(pivot=1))
    d = donnees()
    complet = s.preparer(d, p)
    for fin in range(1, len(d) + 1):
        pd.testing.assert_frame_equal(s.preparer(d.iloc[:fin], p),
                                      complet.iloc[:fin], check_dtype=False)
    achat = complet.iloc[4]
    assert achat["smc_evenement"] == "BOS" and achat["smc_sens"] == "achat"
    assert achat["fvg_bas"] == 12 and achat["fvg_haut"] == 14
    entree = s.entree("EURUSD", achat, p)
    assert entree is not None and entree.module == "SMC"
    baisse = complet.iloc[6]
    assert baisse["smc_evenement"] == "CHoCH"
    assert s.sortir(baisse, "achat")
    assert complet["smc_evenement"].notna().sum() == 2
