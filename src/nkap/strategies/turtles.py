"""Cassures Donchian, sans inclure la clôture courante dans le canal."""
import pandas as pd

from nkap.configuration import Parametres
from nkap.domaine.modeles import Sens, Signal
from nkap.indicateurs.calculs import plus_bas, plus_haut


class Turtles:
    def preparer(self, donnees: pd.DataFrame, p: Parametres) -> pd.DataFrame:
        return donnees.assign(
            haut_entree=plus_haut(donnees["high"], p.entree_turtles),
            bas_entree=plus_bas(donnees["low"], p.entree_turtles),
            haut_sortie=plus_haut(donnees["high"], p.sortie_turtles),
            bas_sortie=plus_bas(donnees["low"], p.sortie_turtles),
        )

    def entree(self, marche: str, ligne: pd.Series, p: Parametres) -> Signal | None:
        sens: Sens
        if ligne["close"] > ligne["haut_entree"]:
            sens = "achat"
        elif ligne["close"] < ligne["bas_entree"]:
            sens = "vente"
        else:
            return None
        return Signal(marche, ligne.name.to_pydatetime(), sens, "TUR", p.stop_atr * ligne["atr"])

    def sortir(self, ligne: pd.Series, sens: Sens) -> bool:
        return bool(ligne["close"] < ligne["bas_sortie"] if sens == "achat"
                    else ligne["close"] > ligne["haut_sortie"])
