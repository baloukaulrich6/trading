"""Journal SQLite des décisions des agents."""
import csv
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


class Greffier:
    def __init__(self, fichier: Path) -> None:
        self.fichier = fichier
        with closing(sqlite3.connect(fichier)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    sequence INTEGER PRIMARY KEY, date_utc TEXT, identifiant TEXT,
                    agent TEXT, acceptee INTEGER, raison TEXT, details TEXT
                )
            """)

    def noter(self, date: datetime, identifiant: str, agent: str, acceptee: bool,
              raison: str, *, details: dict[str, object] | None = None) -> None:
        with closing(sqlite3.connect(self.fichier)) as db, db:
            db.execute("INSERT INTO decisions VALUES (NULL,?,?,?,?,?,?)",
                       (date.isoformat(), identifiant, agent, acceptee, raison,
                        json.dumps(details or {}, ensure_ascii=False, allow_nan=False)))

    def exporter(self, fichier: Path) -> None:
        with (closing(sqlite3.connect(self.fichier)) as db,
              fichier.open("w", encoding="utf-8", newline="") as sortie):
            curseur = db.execute("SELECT * FROM decisions ORDER BY sequence")
            csv_writer = csv.writer(sortie, delimiter=";")
            csv_writer.writerow([colonne[0] for colonne in curseur.description])
            csv_writer.writerows(curseur)
