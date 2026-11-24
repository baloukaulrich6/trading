"""Import et cache local des bougies clôturées."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PRIX = ("open", "high", "low", "close")


def verifier(bougies: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(bougies.index, pd.DatetimeIndex) or bougies.index.tz is None:
        raise ValueError("L'index des bougies doit porter un fuseau horaire.")
    if bougies.empty or bougies.index.hasnans or bougies.index.has_duplicates:
        raise ValueError("Série vide, date absente ou date en double.")
    if not bougies.index.is_monotonic_increasing:
        raise ValueError("Les dates doivent être classées dans l'ordre croissant.")
    if set(PRIX) - set(bougies.columns):
        raise ValueError("Colonnes requises : open, high, low, close.")
    prix = bougies[list(PRIX)].apply(pd.to_numeric)
    if not np.isfinite(prix.to_numpy()).all() or (prix <= 0).any().any():
        raise ValueError("Prix manquant, non fini ou non positif.")
    if ((prix["high"] < prix[["open", "close", "low"]].max(axis=1)) |
            (prix["low"] > prix[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Prix OHLC incohérents.")
    if (prix.index.to_series().diff() > pd.Timedelta(days=5)).any():
        raise ValueError("Trou de plus de cinq jours dans les données D1.")
    return prix


def charger_csv(fichier: Path, *, a_la_date: datetime) -> pd.DataFrame:
    if a_la_date.utcoffset() is None:
        raise ValueError("La date d'évaluation doit porter un fuseau horaire.")
    donnees = pd.read_csv(fichier)
    if "date_utc" not in donnees:
        raise ValueError("Colonne date_utc manquante.")
    donnees.index = pd.to_datetime(donnees.pop("date_utc"), utc=True, format="ISO8601")
    return verifier(donnees.loc[donnees.index <= a_la_date])


def resoudre(noms: set[str], alias: list[str]) -> str | None:
    index = {nom.casefold(): nom for nom in sorted(noms)}
    return next((index[a.casefold()] for a in alias if a.casefold() in index), None)


class CacheBougies:
    def __init__(self, fichier: Path) -> None:
        self.fichier = fichier
        with closing(sqlite3.connect(fichier)) as connexion, connexion:
            connexion.execute("""
                CREATE TABLE IF NOT EXISTS bougies (
                    source TEXT, symbole TEXT, date_utc TEXT,
                    open REAL, high REAL, low REAL, close REAL,
                    PRIMARY KEY (source, symbole, date_utc)
                )
            """)

    def ecrire(self, source: str, symbole: str, donnees: pd.DataFrame) -> None:
        lignes = [
            (source, symbole, date.tz_convert("UTC").isoformat(), *map(float, prix))
            for date, *prix in verifier(donnees).itertuples()
        ]
        with closing(sqlite3.connect(self.fichier)) as connexion, connexion:
            connexion.executemany("INSERT OR REPLACE INTO bougies VALUES (?,?,?,?,?,?,?)", lignes)

    def lire(self, source: str, symbole: str, *, a_la_date: datetime) -> pd.DataFrame:
        if a_la_date.utcoffset() is None:
            raise ValueError("La date d'évaluation doit porter un fuseau horaire.")
        borne = pd.Timestamp(a_la_date).tz_convert("UTC").isoformat()
        with closing(sqlite3.connect(self.fichier)) as connexion:
            donnees = pd.read_sql_query(
                "SELECT date_utc, open, high, low, close FROM bougies "
                "WHERE source = ? AND symbole = ? AND date_utc <= ? ORDER BY date_utc",
                connexion, params=(source, symbole, borne),
            )
        donnees.index = pd.to_datetime(donnees.pop("date_utc"), utc=True, format="ISO8601")
        return verifier(donnees)
