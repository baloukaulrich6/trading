"""Note un signal à partir des résultats nets comparables."""
from dataclasses import dataclass
from math import isfinite
from statistics import mean

from nkap.agents.eclaireur import Observation
from nkap.domaine.modeles import Candidat, Decision


@dataclass(frozen=True)
class Analyse:
    candidat: Candidat | None
    decision: Decision


def analyser(observation: Observation, *, seuil: float = 60.0) -> Analyse:
    r = observation.historique_net_r
    if len(r) < 100 or not all(isfinite(v) for v in r):
        return Analyse(None, Decision(False, "Historique net comparable insuffisant"))
    esperance = mean(r)
    frequence = sum(v > 0 for v in r) / len(r)
    composante_esperance = min(60.0, max(0.0, 60 * esperance))
    composante_frequence = 40 * frequence
    note = composante_esperance + composante_frequence
    raison = (f"Espérance {esperance:.3f} R net, note {note:.1f}/100 "
              f"(espérance {composante_esperance:.1f}/60, fréquence {composante_frequence:.1f}/40)")
    accepte = esperance > 0.1 and note >= seuil
    candidat = Candidat(observation.signal, note, esperance) if accepte else None
    return Analyse(candidat, Decision(accepte, raison))
