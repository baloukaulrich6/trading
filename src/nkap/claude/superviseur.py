"""Revue des résultats hors du chemin d'exécution."""
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nkap.claude.budget import Budget

CONSIGNE = """
Analyse le bilan de trading transmis. Résume les faits mesurés, note les anomalies,
explique les pertes et signale les données insuffisantes. Aucune recommandation
d'achat ou de vente, aucun ordre, aucun changement d'un paramètre.
Retourne uniquement un objet JSON avec resume (texte), post_mortem (liste de textes)
et alertes (liste de textes).
""".strip()


class Revue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume: str = Field(min_length=1, max_length=600)
    post_mortem: list[str] = Field(max_length=8)
    alertes: list[str] = Field(max_length=8)


def superviser(bilan: dict[str, object], budget: Budget, maintenant: datetime,
               transport: Callable[[str, dict[str, object]], tuple[str, int]],
               maximum_micro_usd: int) -> Revue:
    cle = uuid4().hex
    if not budget.reserver(cle, maintenant, maximum_micro_usd):
        raise ValueError("Budget Claude insuffisant pour la revue.")
    texte, cout = transport(CONSIGNE, bilan)
    if not budget.comptabiliser(cle, cout):
        raise ValueError("Coût de la revue supérieur à la réservation.")
    try:
        return Revue.model_validate_json(texte)
    except ValidationError as erreur:
        raise ValueError("Revue Claude non conforme.") from erreur
