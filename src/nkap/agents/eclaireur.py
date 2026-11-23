"""Transforme le signal d'un marché en observation pour le filtre."""
from dataclasses import dataclass

from nkap.domaine.modeles import Signal


@dataclass(frozen=True)
class Observation:
    signal: Signal
    atr: float
    spread: float
    amplitude: float
    retard_prix: float
    marche_ouvert: bool
    historique_net_r: tuple[float, ...]
