"""Seuil de solde HFM et échéance locale pour les nouvelles entrées automatiques."""
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import isfinite
from pathlib import Path

from rapport import DOUALA


@dataclass(frozen=True)
class Objectif:
    cible_usd: float
    date_fin: date

    @classmethod
    def configurer(cls) -> "Objectif | None":
        cible = os.getenv("NKAP_OBJECTIF_USD", "").strip()
        fin = os.getenv("NKAP_OBJECTIF_DATE_FIN", "").strip()
        if not cible and not fin:
            return None
        if not cible or not fin:
            raise ValueError("Renseigne NKAP_OBJECTIF_USD et NKAP_OBJECTIF_DATE_FIN ensemble.")
        montant = float(cible)
        if not isfinite(montant) or montant <= 0:
            raise ValueError("NKAP_OBJECTIF_USD doit être un montant positif.")
        return cls(montant, date.fromisoformat(fin))


class SuiviObjectif:
    def __init__(self, chemin: Path, objectif: Objectif) -> None:
        self.chemin = chemin
        self.objectif = objectif
        with closing(sqlite3.connect(chemin)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS objectifs_hfm (
                    identite TEXT, fin TEXT, cible REAL, atteint INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (identite, fin, cible)
                )
            """)

    def observer(self, identite: str, balance: float, devise: str, maintenant: datetime) -> dict:
        objectif = self.objectif
        devise = devise.upper()
        facteur = {"USD": 1, "USC": 100}.get(devise)
        solde = balance / facteur if facteur and isfinite(balance) else None
        date_fin = objectif.date_fin.isoformat()
        cle = (identite, date_fin, objectif.cible_usd)
        with closing(sqlite3.connect(self.chemin)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO objectifs_hfm(identite, fin, cible) VALUES (?,?,?)", cle)
            atteint, = db.execute(
                "SELECT atteint FROM objectifs_hfm WHERE identite=? AND fin=? AND cible=?", cle
            ).fetchone()
            expire = maintenant.astimezone(DOUALA).date() > objectif.date_fin
            if not atteint and not expire and solde is not None and solde >= objectif.cible_usd:
                db.execute("UPDATE objectifs_hfm SET atteint=1 WHERE identite=? AND fin=? AND cible=?", cle)
                atteint = 1
        motif = None
        if atteint:
            motif = "Objectif de solde atteint : nouvelles entrées arrêtées."
        elif expire:
            motif = "Échéance de l’objectif dépassée : nouvelles entrées arrêtées."
        elif solde is None:
            motif = "Solde USD/USC indisponible : nouvelles entrées arrêtées."
        return {"cible_usd": objectif.cible_usd, "solde_usd": solde, "date_fin": date_fin,
                "bloque": motif is not None, "motif": motif}

    def verifier(self, courtier, compte) -> dict:
        return self.observer(f"{courtier.serveur.casefold()}:{courtier.login}", compte.balance,
                             compte.currency, datetime.now(timezone.utc))
