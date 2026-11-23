"""Horaires locaux des nouvelles entrées Nkap."""
import os
from datetime import datetime, time, timedelta

from rapport import DOUALA

HEURE_DEBUT = "09:00"
HEURE_FIN = "00:00"


def horaires() -> tuple[str, str]:
    return (os.getenv("HEURE_EXECUTION", HEURE_DEBUT).strip(),
            os.getenv("HEURE_LIMITE", HEURE_FIN).strip())


def fenetre_entree(maintenant: datetime) -> bool:
    debut, fin = map(time.fromisoformat, horaires())
    if (debut.tzinfo is not None or fin.tzinfo is not None
            or (debut >= fin and not (fin == time.min < debut))):
        raise ValueError("La fin doit suivre le début. Utilise 00:00 pour minuit en fin de journée.")
    local = maintenant.astimezone(DOUALA)
    return local.weekday() < 5 and local.time() >= debut and (fin == time.min or local.time() < fin)


def prochain_reveil(maintenant: datetime) -> str:
    local = maintenant.astimezone(DOUALA)
    debut = time.fromisoformat(horaires()[0])
    reveil = datetime.combine(local.date(), debut, DOUALA)
    while reveil <= local or reveil.weekday() >= 5:
        reveil += timedelta(days=1)
    return reveil.isoformat()
