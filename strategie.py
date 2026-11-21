"""Règles d'entrée et de sortie : module Turtles (tendance) et module contrarien (cycle)."""
import pandas as pd

import config as C
import indicateurs as ind

TURTLES = "TUR"
CONTRARIEN = "CTR"


def preparer(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute tous les indicateurs aux bougies journalières (bougies clôturées uniquement)."""
    d = df.copy()
    d["atr"] = ind.atr(d, C.ATR_PERIODE)
    d["haut_entree"] = ind.plus_haut(d["high"], C.TURTLES_ENTREE)
    d["bas_entree"] = ind.plus_bas(d["low"], C.TURTLES_ENTREE)
    d["haut_sortie"] = ind.plus_haut(d["high"], C.TURTLES_SORTIE)
    d["bas_sortie"] = ind.plus_bas(d["low"], C.TURTLES_SORTIE)
    d["ebsw"] = ind.even_better_sinewave(d["close"], C.EBSW_DUREE, C.EBSW_LISSAGE)
    d["rsi"] = ind.rsi(d["close"], C.RSI_PERIODE)
    d["sma_longue"] = ind.sma(d["close"], C.SMA_LONGUE)
    d["sma_sortie"] = ind.sma(d["close"], C.SMA_SORTIE)
    d["regime"] = (d["ebsw"].abs() >= C.SEUIL_TENDANCE).map({True: "tendance", False: "cycle"})
    return d


def signal_entree(ligne: pd.Series):
    """Renvoie un signal pour la dernière bougie clôturée, ou None.

    Format : {"sens": "achat"/"vente", "module": TUR/CTR, "stop": prix, "raison": texte}
    """
    colonnes = ["atr", "haut_entree", "bas_entree", "ebsw", "rsi", "sma_longue"]
    if ligne[colonnes].isna().any():
        return None

    cloture = ligne["close"]
    distance = C.STOP_EN_N * ligne["atr"]

    if ligne["regime"] == "tendance":
        if cloture > ligne["haut_entree"]:
            return {"sens": "achat", "module": TURTLES, "stop": cloture - distance,
                    "raison": f"cassure du plus haut {C.TURTLES_ENTREE} jours"}
        if cloture < ligne["bas_entree"]:
            return {"sens": "vente", "module": TURTLES, "stop": cloture + distance,
                    "raison": f"cassure du plus bas {C.TURTLES_ENTREE} jours"}
    else:
        if cloture > ligne["sma_longue"] and ligne["rsi"] < C.RSI_ACHAT:
            return {"sens": "achat", "module": CONTRARIEN, "stop": cloture - distance,
                    "raison": f"RSI {C.RSI_PERIODE} jours à {ligne['rsi']:.1f} en mode cycle"}
        if cloture < ligne["sma_longue"] and ligne["rsi"] > C.RSI_VENTE:
            return {"sens": "vente", "module": CONTRARIEN, "stop": cloture + distance,
                    "raison": f"RSI {C.RSI_PERIODE} jours à {ligne['rsi']:.1f} en mode cycle"}
    return None


def doit_sortir(ligne: pd.Series, sens: str, module: str) -> bool:
    """Sortie selon la règle du module qui a ouvert la position (le stop reste chez le courtier)."""
    cloture = ligne["close"]
    if module == TURTLES:
        if sens == "achat":
            return cloture < ligne["bas_sortie"]
        return cloture > ligne["haut_sortie"]
    if module == CONTRARIEN:
        if sens == "achat":
            return cloture > ligne["sma_sortie"]
        return cloture < ligne["sma_sortie"]
    return False
