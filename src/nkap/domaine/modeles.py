"""Représentations typées des échanges entre les agents."""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Sens = Literal["achat", "vente"]
Module = Literal["TUR", "CTR"]


@dataclass(frozen=True)
class Bougie:
    date: datetime
    ouverture: float
    haut: float
    bas: float
    cloture: float


@dataclass(frozen=True)
class Signal:
    marche: str
    date: datetime
    sens: Sens
    module: Module
    distance_stop: float


@dataclass(frozen=True)
class Candidat:
    signal: Signal
    note: float
    esperance_nette_r: float


@dataclass(frozen=True)
class Decision:
    autorisee: bool
    raison: str


@dataclass(frozen=True)
class Ordre:
    identifiant: str
    signal: Signal
    volume: float
    prix: float
    stop: float


@dataclass(frozen=True)
class Position:
    marche: str
    sens: Sens
    risque: float
    expositions: tuple[tuple[str, Sens], ...]


@dataclass(frozen=True)
class Trade:
    signal: Signal
    date_entree: datetime
    date_sortie: datetime
    resultat_r: float
    resultat_usd: float
    motif: str
