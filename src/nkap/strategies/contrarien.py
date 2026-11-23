"""Retour vers la moyenne avec filtre de tendance longue."""
import pandas as pd

from nkap.configuration import Parametres
from nkap.domaine.modeles import Sens, Signal
from nkap.indicateurs.calculs import rsi, sma


class Contrarien:
    def preparer(self, donnees: pd.DataFrame, p: Parametres) -> pd.DataFrame:
        return donnees.assign(
            rsi=rsi(donnees["close"], p.periode_rsi),
            sma_longue=sma(donnees["close"], p.sma_longue),
            sma_sortie=sma(donnees["close"], p.sma_sortie),
        )

    def entree(self, marche: str, ligne: pd.Series, p: Parametres) -> Signal | None:
        sens: Sens
        if ligne["close"] > ligne["sma_longue"] and ligne["rsi"] < p.rsi_achat:
            sens = "achat"
        elif ligne["close"] < ligne["sma_longue"] and ligne["rsi"] > p.rsi_vente:
            sens = "vente"
        else:
            return None
        return Signal(marche, ligne.name.to_pydatetime(), sens, "CTR", p.stop_atr * ligne["atr"])

    def sortir(self, ligne: pd.Series, sens: Sens) -> bool:
        return bool(ligne["close"] > ligne["sma_sortie"] if sens == "achat"
                    else ligne["close"] < ligne["sma_sortie"])
