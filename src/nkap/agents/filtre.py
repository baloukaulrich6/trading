"""Applique les règles d'éligibilité, sans choisir de volume."""
from math import isfinite

from nkap.agents.eclaireur import Observation
from nkap.agents.meteo import Meteo
from nkap.domaine.modeles import Decision


def filtrer(o: Observation, meteo: Meteo, *, en_pause: bool, pari_risque: bool) -> Decision:
    chiffres = (o.atr, o.spread, o.amplitude, o.retard_prix)
    if not all(isfinite(v) and v >= 0 for v in chiffres) or o.atr <= 0:
        return Decision(False, "Données de marché invalides")
    refus = (
        (not o.marche_ouvert, "Marché fermé"),
        (en_pause, "Pause de risque"),
        (o.spread > 0.10 * o.atr, "Spread supérieur à 10 % de l’ATR"),
        (o.amplitude > 3 * o.atr, "Bougie de choc"),
        (o.retard_prix > o.atr, "Cassure dépassée"),
        (meteo.peur and pari_risque, "Contexte défavorable à cette exposition"),
    )
    return next((Decision(False, motif) for interdit, motif in refus if interdit),
                Decision(True, "Éligible"))
