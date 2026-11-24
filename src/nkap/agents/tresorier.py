"""Dimensionne une proposition puis applique les limites versionnées."""
from dataclasses import dataclass
from math import floor, isfinite

from nkap.configuration import Limites
from nkap.domaine.modeles import Candidat, Decision, Ordre, Sens
from nkap.risque.limites import EtatRisque, autoriser


@dataclass(frozen=True)
class Taille:
    prix: float
    perte_par_lot: float
    lot_min: float
    pas: float
    expositions: tuple[tuple[str, Sens], ...]


def dimensionner(candidat: Candidat, taille: Taille, etat: EtatRisque, limites: Limites,
                 *, identifiant: str, meteo_peur: bool) -> tuple[Ordre | None, Decision]:
    valeurs = (taille.prix, taille.perte_par_lot, taille.lot_min, taille.pas,
               etat.capital, candidat.signal.distance_stop)
    if not all(isfinite(v) and v > 0 for v in valeurs):
        return None, Decision(False, "Données de taille invalides")
    fraction = limites.risque_base
    if etat.pertes_consecutives >= limites.reduire_apres:
        fraction /= 2
    if meteo_peur:
        fraction /= 2
    volume = floor(etat.capital * fraction / taille.perte_par_lot / taille.pas) * taille.pas
    if volume < taille.lot_min:
        return None, Decision(False, "Lot minimal hors budget")
    decision = autoriser(etat, volume * taille.perte_par_lot, taille.expositions, limites)
    signal = candidat.signal
    stop = taille.prix + (-1 if signal.sens == "achat" else 1) * signal.distance_stop
    if stop <= 0:
        return None, Decision(False, "Stop non positif")
    ordre = Ordre(identifiant, signal, volume, taille.prix, stop) if decision.autorisee else None
    return ordre, decision
