"""Réserve une décision sur disque avant un envoi et traite les réponses ambiguës."""
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal, Protocol

from nkap.configuration import Local
from nkap.domaine.modeles import Ordre

EtatEnvoi = Literal["execute", "refuse", "incertain"]


@dataclass(frozen=True)
class Reponse:
    etat: EtatEnvoi
    raison: str
    ticket: str | None = None


@dataclass(frozen=True)
class Compte:
    identifiant: str
    demo: bool


@dataclass(frozen=True)
class Validation:
    hors_echantillon: bool = False
    reserve: bool = False
    jours_demo: int = 0
    approuve: bool = False

    def engageable(self) -> bool:
        return self.hors_echantillon and self.reserve and self.jours_demo >= 7 and self.approuve


class Courtier(Protocol):
    def compte(self) -> Compte: ...
    def disponible(self, ordre: Ordre) -> bool: ...
    def envoyer(self, ordre: Ordre) -> Reponse: ...
    def rechercher(self, identifiant: str) -> Reponse: ...


class Executeur:
    def __init__(self, base: Path, courtier: Courtier) -> None:
        self.base = base
        self.courtier = courtier
        with closing(sqlite3.connect(base)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS envois (
                    compte TEXT, identifiant TEXT, statut TEXT, ticket TEXT,
                    PRIMARY KEY (compte, identifiant)
                )
            """)

    def _reserver(self, compte: str, cle: str) -> bool:
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM envois WHERE compte = ? AND statut = 'incertain'",
                          (compte,)).fetchone() is not None:
                return False
            return db.execute("INSERT OR IGNORE INTO envois VALUES (?,?,?,NULL)",
                              (compte, cle, "incertain")).rowcount == 1

    def _confirmer(self, compte: str, cle: str, reponse: Reponse) -> None:
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute("UPDATE envois SET statut = ?, ticket = ? WHERE compte = ? AND identifiant = ?",
                       (reponse.etat, reponse.ticket, compte, cle))

    def executer(self, ordre: Ordre, compte_attendu: str, local: Local, validation: Validation) -> Reponse:
        if local.mode == "TEST":
            return Reponse("refuse", "Mode TEST")
        compte = self.courtier.compte()
        if compte.identifiant != compte_attendu or not compte_attendu:
            return Reponse("refuse", "Compte différent de la configuration")
        if (local.mode == "DEMO") != compte.demo:
            return Reponse("refuse", "Type de compte incompatible avec le mode")
        if local.mode == "REEL" and not (local.confirmation_reelle and validation.engageable()):
            return Reponse("refuse", "Validation réelle incomplète")
        valeurs = (ordre.volume, ordre.prix, ordre.stop)
        if not all(isfinite(v) and v > 0 for v in valeurs):
            return Reponse("refuse", "Ordre ou stop invalide")
        sens_stop = ordre.stop < ordre.prix if ordre.signal.sens == "achat" else ordre.stop > ordre.prix
        if not sens_stop:
            return Reponse("refuse", "Stop du mauvais côté")
        if not self.courtier.disponible(ordre):
            return Reponse("refuse", "Position existante ou précontrôle courtier refusé")
        if not self._reserver(compte.identifiant, ordre.identifiant):
            return Reponse("refuse", "Ordre déjà traité ou rapprochement en attente")
        try:
            reponse = self.courtier.envoyer(ordre)
        except (OSError, RuntimeError):
            return Reponse("incertain", "Envoi interrompu, rapprochement obligatoire")
        if reponse.etat == "execute" and not reponse.ticket:
            return Reponse("incertain", "Exécution sans ticket, rapprochement obligatoire")
        self._confirmer(compte.identifiant, ordre.identifiant, reponse)
        return reponse

    def reconcilier(self, compte_attendu: str) -> bool:
        if self.courtier.compte().identifiant != compte_attendu:
            return False
        with closing(sqlite3.connect(self.base)) as db:
            incertains = db.execute(
                "SELECT identifiant FROM envois WHERE compte = ? AND statut = 'incertain'",
                (compte_attendu,),
            ).fetchall()
        complet = True
        for (cle,) in incertains:
            reponse = self.courtier.rechercher(cle)
            if reponse.etat == "incertain" or (reponse.etat == "execute" and not reponse.ticket):
                complet = False
                continue
            self._confirmer(compte_attendu, cle, reponse)
        return complet
