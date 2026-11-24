"""Frontière Claude injectée, avec veto JSON strict et réservation avant tout appel."""
from collections.abc import Callable
from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nkap.claude.budget import Budget
from nkap.domaine.modeles import Decision, Ordre


class ReponseVeto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["autoriser", "bloquer"]
    raison: str = Field(min_length=1, max_length=300)


class ClientVeto:
    def __init__(self, budget: Budget, transport: Callable[[Ordre], tuple[str, int]],
                 horloge: Callable[[], datetime], maximum_micro_usd: int) -> None:
        self.budget = budget
        self.transport = transport
        self.horloge = horloge
        self.maximum = maximum_micro_usd

    def __call__(self, ordre: Ordre) -> Decision:
        cle = uuid4().hex
        if not self.budget.reserver(cle, self.horloge(), self.maximum):
            return Decision(False, "Budget Claude épuisé")
        try:
            texte, cout = self.transport(ordre)
        except (OSError, RuntimeError, ValueError):
            return Decision(False, "Claude indisponible : réservation conservée")
        if cout < 0 or not self.budget.comptabiliser(cle, cout):
            return Decision(False, "Coût Claude hors du plafond réservé")
        try:
            avis = ReponseVeto.model_validate_json(texte)
        except ValidationError:
            return Decision(False, "Réponse Claude non conforme")
        if not avis.raison.strip():
            return Decision(False, "Raison du veto absente")
        return Decision(avis.decision == "autoriser", avis.raison)
