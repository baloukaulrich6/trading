"""Sélection du module selon un détecteur évalué en recherche."""
import pandas as pd

from nkap.configuration import Parametres
from nkap.indicateurs.calculs import atr, efficiency_ratio, even_better_sinewave
from nkap.strategies.contrarien import Contrarien
from nkap.strategies.turtles import Turtles


def preparer(donnees: pd.DataFrame, p: Parametres) -> pd.DataFrame:
    d = Contrarien().preparer(Turtles().preparer(donnees, p), p)
    if p.regime == "er":
        mesure = efficiency_ratio(d["close"], p.periode_er)
        seuil = p.seuil_er
    else:
        mesure = even_better_sinewave(d["close"]).abs()
        seuil = p.seuil_ebsw
    return d.assign(atr=atr(d, p.periode_atr), tendance=(mesure >= seuil).where(mesure.notna()))
