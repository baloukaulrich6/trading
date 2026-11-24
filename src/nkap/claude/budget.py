"""Réservation transactionnelle en millionièmes de dollar, sans arrondi binaire."""
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


class Budget:
    def __init__(self, fichier: Path, plafond_micro_usd: int) -> None:
        if plafond_micro_usd < 0:
            raise ValueError("Budget négatif")
        self.fichier = fichier
        self.plafond = plafond_micro_usd
        with closing(sqlite3.connect(fichier)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS appels_claude (
                    demande TEXT PRIMARY KEY, mois TEXT, maximum INTEGER, cout INTEGER
                )
            """)

    def reserver(self, cle: str, horodatage: datetime, maximum: int) -> bool:
        if maximum <= 0 or horodatage.utcoffset() is None:
            raise ValueError("Réservation de budget invalide")
        mois = horodatage.astimezone(UTC).strftime("%Y-%m")
        with closing(sqlite3.connect(self.fichier)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            employe, = db.execute(
                "SELECT COALESCE(SUM(COALESCE(cout, maximum)), 0) FROM appels_claude WHERE mois = ?",
                (mois,),
            ).fetchone()
            if employe + maximum > self.plafond:
                return False
            return db.execute("INSERT OR IGNORE INTO appels_claude VALUES (?,?,?,NULL)",
                              (cle, mois, maximum)).rowcount == 1

    def comptabiliser(self, cle: str, cout: int) -> bool:
        if cout < 0:
            raise ValueError("Coût négatif")
        with closing(sqlite3.connect(self.fichier)) as db, db:
            ligne = db.execute("SELECT maximum FROM appels_claude WHERE demande = ?", (cle,)).fetchone()
            if ligne is None:
                raise ValueError("Appel sans réservation")
            db.execute("UPDATE appels_claude SET cout = ? WHERE demande = ?", (cout, cle))
            return cout <= ligne[0]
