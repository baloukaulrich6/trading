"""Observe les signaux D1 et mesure leur évolution sans exécuter d'ordre."""
import csv
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd

from nkap.configuration import Parametres
from nkap.domaine.modeles import Sens, Signal
from nkap.donnees.bougies import verifier
from nkap.strategies.contrarien import Contrarien
from nkap.strategies.regime import preparer
from nkap.strategies.turtles import Turtles


class Fantome:
    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin
        with closing(sqlite3.connect(chemin)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    source TEXT, marche TEXT, version TEXT, bougie TEXT,
                    observee TEXT, decision TEXT, sens TEXT, module TEXT,
                    stop_distance REAL, rapport TEXT,
                    PRIMARY KEY (source, marche, version, bougie)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS resultats (
                    source TEXT, marche TEXT, version TEXT, bougie TEXT,
                    horizon INTEGER, resultat_brut_r REAL, entree REAL, sortie REAL,
                    PRIMARY KEY (source, marche, version, bougie, horizon)
                )
            """)

    def observer(self, source: str, marche: str, bougies: pd.DataFrame,
                 params: Parametres, maintenant: datetime) -> dict[str, object]:
        if maintenant.utcoffset() is None:
            raise ValueError("Horodatage d'observation sans fuseau.")
        d = preparer(verifier(bougies), params)
        if d.index[-1] > maintenant:
            raise ValueError("Bougie future dans le flux MT5.")
        ligne = d.iloc[-1]
        signal: Signal | None = None
        if pd.notna(ligne["tendance"]) and ligne["atr"] > 0:
            strategie = Turtles() if ligne["tendance"] else Contrarien()
            signal = strategie.entree(marche, ligne, params)
        date = ligne.name.isoformat()
        rapport: dict[str, object] = {
            "marche": marche, "version": params.version, "bougie": date,
            "cloture": float(ligne["close"]),
            "signal": signal.sens if signal else None,
            "module": signal.module if signal else None,
            "motif": "Signal brut observé sans ordre" if signal else "Aucun signal D1",
        }
        with closing(sqlite3.connect(self.chemin)) as db, db:
            db.execute("INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)", (
                source, marche, params.version, date, maintenant.isoformat(), rapport["motif"],
                signal.sens if signal else None, signal.module if signal else None,
                signal.distance_stop if signal else None, json.dumps(rapport, ensure_ascii=False),
            ))
            self._mesurer(db, source, marche, d)
        return rapport

    @staticmethod
    def _mesurer(db: sqlite3.Connection, source: str, marche: str, bougies: pd.DataFrame) -> None:
        lignes = db.execute(
            "SELECT version, bougie, observee, sens, stop_distance FROM observations "
            "WHERE source=? AND marche=? AND sens IS NOT NULL AND bougie>=?",
            (source, marche, bougies.index[0].isoformat()),
        )
        for version, date, observee, sens, distance in lignes:
            suivantes = bougies.loc[(bougies.index > pd.Timestamp(date))
                                    & (bougies.index >= pd.Timestamp(observee))]
            for horizon in (1, 5):
                if len(suivantes) >= horizon:
                    entree, sortie, gain = resultat_au_stop(suivantes.iloc[:horizon], sens, distance)
                    db.execute("INSERT OR IGNORE INTO resultats VALUES (?,?,?,?,?,?,?,?)",
                               (source, marche, version, date, horizon, gain, entree, sortie))

    def exporter(self, fichier: Path) -> None:
        with (closing(sqlite3.connect(self.chemin)) as db,
              fichier.open("w", encoding="utf-8", newline="") as sortie):
            lignes = db.execute("""
                SELECT o.source, o.marche, o.version, o.bougie, o.observee, o.decision,
                       o.sens, o.module, r.horizon, r.resultat_brut_r
                  FROM observations o LEFT JOIN resultats r USING (source, marche, version, bougie)
                 ORDER BY o.bougie, o.marche, r.horizon
            """)
            writer = csv.writer(sortie, delimiter=";")
            writer.writerow([c[0] for c in lignes.description])
            writer.writerows(lignes)


def resultat_au_stop(d: pd.DataFrame, sens: Sens, distance: float) -> tuple[float, float, float]:
    entree = float(d.iloc[0]["open"])
    signe = 1 if sens == "achat" else -1
    stop = entree - signe * distance
    sortie = float(d.iloc[-1]["close"])
    for bougie in d.itertuples():
        if sens == "achat" and bougie.low <= stop:
            sortie = min(stop, bougie.open)
            break
        if sens == "vente" and bougie.high >= stop:
            sortie = max(stop, bougie.open)
            break
    return entree, sortie, signe * (sortie - entree) / distance
