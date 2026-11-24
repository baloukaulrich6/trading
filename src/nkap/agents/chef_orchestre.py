"""Relais des agents sans connexion directe au courtier."""
from collections.abc import Callable
from datetime import datetime

from nkap.agents.analyste import analyser
from nkap.agents.eclaireur import Observation
from nkap.agents.filtre import filtrer
from nkap.agents.meteo import Meteo
from nkap.agents.tresorier import Taille, dimensionner
from nkap.configuration import Limites
from nkap.domaine.modeles import Decision, Ordre
from nkap.risque.limites import EtatRisque
from nkap.stockage.greffier import Greffier


def evaluer(observation: Observation, meteo: Meteo, etat: EtatRisque, taille: Taille,
            limites: Limites, greffier: Greffier, horloge: Callable[[], datetime],
            veto: Callable[[Ordre], Decision], *, pari_risque: bool, compte: str) -> Ordre | None:
    signal = observation.signal
    cle = f"{compte}:{signal.marche}:{signal.date.isoformat()}"
    date = horloge()
    greffier.noter(date, cle, "Éclaireur", True, f"{signal.module} · {signal.sens}")
    filtre = filtrer(observation, meteo, en_pause=etat.pause, pari_risque=pari_risque)
    greffier.noter(date, cle, "Filtre", filtre.autorisee, filtre.raison)
    if not filtre.autorisee:
        return None
    analyse = analyser(observation)
    greffier.noter(date, cle, "Analyste", analyse.decision.autorisee, analyse.decision.raison)
    if analyse.candidat is None:
        return None
    ordre, decision = dimensionner(analyse.candidat, taille, etat, limites, identifiant=cle,
                                   meteo_peur=meteo.peur)
    greffier.noter(date, cle, "Trésorier", decision.autorisee, decision.raison)
    if ordre is None:
        return None
    try:
        avis = veto(ordre)
    except (OSError, RuntimeError, ValueError):
        avis = Decision(False, "Veto indisponible")
    greffier.noter(horloge(), cle, "Veto", avis.autorisee, avis.raison)
    return ordre if avis.autorisee else None
