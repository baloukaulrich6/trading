"""Décrit le contexte à partir de rendements déjà calculés."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Meteo:
    peur: bool
    explication: str


def observer(actions: float, or_usd: float, yen: float, bitcoin: float,
             volatilite: float) -> Meteo:
    valeurs = (actions, or_usd, yen, bitcoin, volatilite)
    if not all(isfinite(v) for v in valeurs):
        return Meteo(True, "Contexte multi-marchés incomplet")
    votes = sum((actions < 0, or_usd > 0, yen > 0, bitcoin < 0, volatilite > 0))
    return Meteo(votes >= 4, f"{votes}/5 marchés orientés vers l'aversion au risque")
