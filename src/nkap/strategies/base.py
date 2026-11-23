"""Contrat partagé par les stratégies."""
from typing import Protocol

import pandas as pd

from nkap.configuration import Parametres
from nkap.domaine.modeles import Sens, Signal


class Strategie(Protocol):
    def preparer(self, donnees: pd.DataFrame, p: Parametres) -> pd.DataFrame: ...
    def entree(self, marche: str, ligne: pd.Series, p: Parametres) -> Signal | None: ...
    def sortir(self, ligne: pd.Series, sens: Sens) -> bool: ...
