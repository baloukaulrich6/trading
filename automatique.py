"""Surveillance D1 en arrière-plan, via le Planificateur de tâches Windows."""
import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import sleep

import MetaTrader5 as mt5

import config as C
import robot

BASE = Path(__file__).resolve().parent
ETAT = BASE / "automatique_etat.json"
INTERVALLE = 60


class Planificateur:
    def __init__(self):
        with closing(sqlite3.connect(BASE / "automatique.sqlite3")) as connexion, connexion:
            connexion.execute("""
                CREATE TABLE IF NOT EXISTS passages (
                    serveur TEXT, compte INTEGER, symbole TEXT, bougie TEXT, mode TEXT,
                    PRIMARY KEY (serveur, compte, symbole, bougie, mode)
                )
            """)
        self.rapports = []
        self.observations = {}

    def nouveau(self, courtier, symbole, bougie, solde, positions):
        cle = (courtier.serveur.casefold(), courtier.login, symbole)
        observation = (bougie, solde, tuple(p.ticket for p in positions))
        precedent = self.observations.get(cle)
        self.observations[cle] = observation
        return observation != precedent

    def reserver(self, courtier, symbole, bougie):
        """Réserve le passage avant toute décision afin d'éviter un doublon après redémarrage."""
        with closing(sqlite3.connect(BASE / "automatique.sqlite3")) as connexion, connexion:
            ligne = connexion.execute(
                "INSERT OR IGNORE INTO passages VALUES (?, ?, ?, ?, ?)",
                (courtier.serveur.casefold(), courtier.login, symbole, bougie.isoformat(), C.MODE),
            )
            return ligne.rowcount == 1

    def relever(self, courtier, compte):
        maintenant = datetime.now(timezone.utc)
        debut = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
        transactions = mt5.history_deals_get(debut, maintenant + timedelta(seconds=1))
        net = None
        nombre = None
        if transactions is not None:
            propres = [d for d in transactions if d.magic == C.MAGIC]
            net = sum(d.profit + d.commission + d.swap + d.fee for d in propres)
            nombre = len(propres)
        self.rapports.append({
            "courtier": courtier.nom,
            "devise": compte.currency,
            "capital": compte.equity,
            "positions": len(courtier.positions()),
            "resultat": net,
            "transactions": nombre,
        })

    def publier(self, statut):
        etat = {"mode": C.MODE, "statut": statut, "heure": datetime.now(timezone.utc).isoformat(),
                "rapports": self.rapports}
        temporaire = ETAT.with_suffix(".tmp")
        temporaire.write_text(json.dumps(etat, ensure_ascii=False), encoding="utf-8")
        temporaire.replace(ETAT)
        dossier = BASE / "rapports_automatiques"
        dossier.mkdir(exist_ok=True)
        date = etat["heure"][:10]
        fichier = dossier / f"{date}.json"
        temporaire = fichier.with_suffix(".tmp")
        temporaire.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
        temporaire.replace(fichier)


def main():
    robot.configurer_log()
    planificateur = Planificateur()
    actifs = [conf for conf in C.COURTIERS if conf["actif"]]
    while True:
        planificateur.rapports.clear()
        erreurs = []
        for conf in actifs:
            try:
                robot.traiter_courtier(conf, planificateur)
            except Exception as erreur:
                logging.getLogger("robot").exception("Passage automatique HFM/MT5 en échec")
                erreurs.append(f"{conf['nom']} : {erreur}")
        statut = "Surveillance des clôtures D1" if actifs else "Aucun courtier actif"
        try:
            planificateur.publier(" | ".join(erreurs) or statut)
        except OSError:
            logging.getLogger("robot").exception("Publication du rapport impossible")
        sleep(INTERVALLE)


if __name__ == "__main__":
    main()
