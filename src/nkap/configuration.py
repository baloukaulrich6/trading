"""Chargement explicite des fichiers versionnés et des options locales."""
import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Modele(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Limites(Modele):
    risque_base: float = Field(gt=0, le=0.01)
    risque_absolu: float = Field(gt=0, le=0.015)
    risque_total: float = Field(gt=0, le=0.04)
    positions_max: int = Field(gt=0, le=4)
    exposition_max: int = Field(gt=0, le=2)
    perte_jour_max: float = Field(gt=0, le=0.03)
    reduire_apres: int = Field(gt=0, le=2)
    pause_apres: int = Field(gt=0, le=5)
    drawdown_max: float = Field(gt=0, le=0.20)

    @model_validator(mode="after")
    def verifier_coherence(self) -> "Limites":
        if not self.risque_base <= self.risque_absolu <= self.risque_total:
            raise ValueError("Les plafonds de risque doivent être croissants.")
        if self.reduire_apres >= self.pause_apres:
            raise ValueError("La réduction du risque doit précéder la pause.")
        return self


class Parametres(Modele):
    version: str = Field(min_length=1)
    entree_turtles: int = Field(ge=2)
    sortie_turtles: int = Field(ge=2)
    stop_atr: float = Field(gt=0)
    periode_atr: int = Field(ge=2)
    periode_rsi: int = Field(ge=2)
    rsi_achat: float = Field(ge=0, lt=50)
    rsi_vente: float = Field(gt=50, le=100)
    sma_longue: int = Field(ge=2)
    sma_sortie: int = Field(ge=2)
    regime: Literal["ebsw", "er"]
    seuil_ebsw: float = Field(gt=0, le=1)
    seuil_er: float = Field(gt=0, le=1)
    periode_er: int = Field(ge=2)


class Marche(Modele):
    symbole: str = Field(min_length=1)
    categorie: Literal["forex", "metal", "indice", "crypto"]
    alias: dict[str, list[str]]


class Marches(Modele):
    marches: list[Marche] = Field(min_length=1)

    @model_validator(mode="after")
    def verifier_univers(self) -> "Marches":
        if len({m.symbole for m in self.marches}) != len(self.marches):
            raise ValueError("Le fichier contient des marchés en double.")
        return self


class Local(Modele):
    mode: Literal["TEST", "DEMO", "REEL"] = "TEST"
    confirmation_reelle: bool = False
    budget_claude_usd: float = Field(default=2.0, ge=0, allow_inf_nan=False)
    cle_claude: SecretStr = SecretStr("")

    @classmethod
    def charger(cls, fichier: Path) -> "Local":
        load_dotenv(fichier)
        return cls.model_validate({
            "mode": os.getenv("NKAP_MODE", "TEST").strip().upper(),
            "confirmation_reelle": os.getenv("COMPTE_REEL_CONFIRME", "").strip().lower() == "oui",
            "budget_claude_usd": os.getenv("NKAP_BUDGET_CLAUDE_USD", "2"),
            "cle_claude": os.getenv("ANTHROPIC_API_KEY", ""),
        })


def lire_yaml(fichier: Path) -> object:
    """Lit un fichier YAML avec le chargeur sans objets Python."""
    return yaml.safe_load(fichier.read_text(encoding="utf-8"))


def charger_config(dossier: Path) -> tuple[Marches, Parametres, Limites]:
    return (
        Marches.model_validate(lire_yaml(dossier / "marches.yaml")),
        Parametres.model_validate(lire_yaml(dossier / "parametres.yaml")),
        Limites.model_validate(lire_yaml(dossier / "limites_risque.yaml")),
    )
