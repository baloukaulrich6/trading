"""Enregistre la validation d'un challenger et exige une promotion humaine."""
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path

from nkap.backtest.metriques import Mesures
from nkap.backtest.walk_forward import Evaluation
from nkap.configuration import Parametres


@dataclass(frozen=True)
class Fantome:
    debut: datetime
    fin: datetime
    sans_ordres: bool
    mesures: Mesures


def admissible(champion: Mesures, challenger: Evaluation, fantome: Fantome) -> bool:
    nouveau = challenger.mesures
    if challenger.refus or champion.calmar is None or nouveau.calmar is None:
        return False
    return (
        isfinite(champion.calmar) and champion.calmar > 0
        and isfinite(nouveau.calmar) and nouveau.calmar >= 1.10 * champion.calmar
        and nouveau.drawdown <= champion.drawdown
        and fantome.fin - fantome.debut >= timedelta(weeks=4)
        and fantome.sans_ordres and fantome.mesures.trades > 0 and fantome.mesures.profit_usd > 0
        and fantome.mesures.drawdown <= champion.drawdown
    )


def proposer(champion: Parametres, version: str, changements: dict[str, object]) -> Parametres:
    bornes = {"entree_turtles": (15, 30), "sortie_turtles": (7, 15),
              "rsi_achat": (5, 15), "rsi_vente": (85, 95), "sma_sortie": (3, 8),
              "seuil_er": (0.25, 0.50), "seuil_ebsw": (0.75, 0.95)}
    if not changements or not set(changements) <= {*bornes, "regime"}:
        raise ValueError("Paramètre hors de l'espace d'adaptation.")
    for cle in set(changements) & bornes.keys():
        valeur = changements[cle]
        minimum, maximum = bornes[cle]
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or not minimum <= valeur <= maximum:
            raise ValueError(f"Valeur hors limites : {cle}.")
    if version == champion.version:
        raise ValueError("Nouvelle version requise.")
    return Parametres.model_validate({**champion.model_dump(), **changements, "version": version})


class Versions:
    def __init__(self, fichier: Path, initial: Parametres) -> None:
        self.fichier = fichier
        with closing(sqlite3.connect(fichier)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    sequence INTEGER PRIMARY KEY, version TEXT NOT NULL UNIQUE,
                    precede INTEGER, acteur TEXT NOT NULL, date TEXT NOT NULL, parametres TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS champion (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    sequence INTEGER NOT NULL, facteur_risque REAL NOT NULL
                )
            """)
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM champion").fetchone() is None:
                db.execute("INSERT INTO versions VALUES (1,?,NULL,'initial','',?)",
                           (initial.version, initial.model_dump_json()))
                db.execute("INSERT INTO champion VALUES (1,1,1)")

    def courant(self) -> tuple[Parametres, float]:
        with closing(sqlite3.connect(self.fichier)) as db:
            donnees, facteur = db.execute(
                "SELECT v.parametres, c.facteur_risque FROM champion c JOIN versions v USING (sequence)"
            ).fetchone()
        return Parametres.model_validate_json(donnees), float(facteur)

    def promouvoir(self, p: Parametres, evaluation_champion: Mesures, evaluation: Evaluation,
                   fantome: Fantome, *, operateur: str, date: datetime, confirme: bool) -> bool:
        if not confirme or not operateur.strip() or not admissible(evaluation_champion, evaluation, fantome):
            return False
        with closing(sqlite3.connect(self.fichier)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            precedent, = db.execute("SELECT sequence FROM champion").fetchone()
            curseur = db.execute("INSERT OR IGNORE INTO versions VALUES (NULL,?,?,?,?,?)",
                                 (p.version, precedent, operateur, date.isoformat(), p.model_dump_json()))
            if curseur.rowcount != 1:
                return False
            db.execute("UPDATE champion SET sequence = ?, facteur_risque = 1", (curseur.lastrowid,))
            return True

    def retrograder(self, *, drawdown_reel: float, drawdown_teste: float,
                    facteur_profit_30: float, trades: int) -> bool:
        if drawdown_reel <= 1.5 * drawdown_teste and (trades < 30 or facteur_profit_30 >= .8):
            return False
        with closing(sqlite3.connect(self.fichier)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            precedent, facteur = db.execute(
                "SELECT v.precede, c.facteur_risque FROM champion c JOIN versions v USING (sequence)"
            ).fetchone()
            if facteur <= .5:
                return False
            if precedent is None:
                db.execute("UPDATE champion SET facteur_risque = .5")
            else:
                db.execute("UPDATE champion SET sequence = ?, facteur_risque = .5", (precedent,))
            return True
