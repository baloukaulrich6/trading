"""Sélection des marchés du robot et des rapports."""
import os

import config as C


def marches(courtier: str) -> tuple[str, ...]:
    """Univers HFM configurable, avec les symboles de base sans suffixe."""
    if courtier != "HFM":
        return tuple(C.SYMBOLES)
    valeur = os.getenv("HFM_MARCHES", "").strip()
    valeurs = valeur.split(",") if valeur else [*C.SYMBOLES, "AUDUSD", "USDCHF", "BTCUSD", "ETHUSD"]
    return tuple(dict.fromkeys(s.strip().upper() for s in valeurs if s.strip()))
