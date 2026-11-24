"""Propose un stop protecteur à partir du risque initial, sans le reculer."""
from math import isfinite

from nkap.domaine.modeles import Sens


def proposer_stop(sens: Sens, entree: float, prix: float,
                  risque_initial: float, stop_actuel: float) -> float | None:
    if not all(isfinite(v) and v > 0 for v in (entree, prix, risque_initial, stop_actuel)):
        return None
    signe = 1 if sens == "achat" else -1
    gain = (prix - entree) * signe / risque_initial
    if gain < 1:
        return None
    stop = entree if gain < 2 else prix - signe * risque_initial
    if stop <= 0 or (stop - stop_actuel) * signe <= 0:
        return None
    return stop
