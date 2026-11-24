"""Vérifications sans effets de bord avant une nouvelle exposition."""
from dataclasses import dataclass
from math import isfinite

from nkap.configuration import Limites
from nkap.domaine.modeles import Decision, Position, Sens


@dataclass(frozen=True)
class EtatRisque:
    capital: float
    sommet: float
    capital_debut_jour: float
    pertes_consecutives: int
    positions: tuple[Position, ...] = ()
    pause: bool = False


def autoriser(etat: EtatRisque, risque: float, expositions: tuple[tuple[str, Sens], ...],
              limites: Limites) -> Decision:
    valeurs = (etat.capital, etat.sommet, etat.capital_debut_jour, risque)
    if not all(isfinite(v) and v > 0 for v in valeurs):
        return Decision(False, "Capital, référence ou risque invalide")
    if etat.pause or etat.pertes_consecutives >= limites.pause_apres:
        return Decision(False, "Pause ou série de pertes")
    if etat.capital < etat.sommet * (1 - limites.drawdown_max):
        return Decision(False, "Coupe-circuit sous le sommet")
    if etat.capital <= etat.capital_debut_jour * (1 - limites.perte_jour_max):
        return Decision(False, "Limite de perte du jour")
    if len(etat.positions) >= limites.positions_max:
        return Decision(False, "Nombre maximal de positions")
    plafond = min(limites.risque_base, limites.risque_absolu)
    if etat.pertes_consecutives >= limites.reduire_apres:
        plafond /= 2
    if risque > etat.capital * plafond:
        return Decision(False, "Risque par position")
    if any(not isfinite(p.risque) or p.risque < 0 for p in etat.positions):
        return Decision(False, "Risque des positions inconnu")
    if risque + sum(p.risque for p in etat.positions) > etat.capital * limites.risque_total:
        return Decision(False, "Risque total engagé")
    if any(sum(exposition in p.expositions for p in etat.positions) >= limites.exposition_max
           for exposition in expositions):
        return Decision(False, "Exposition dans le même sens")
    return Decision(True, "Limites respectées")
