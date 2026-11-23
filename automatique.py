"""Surveillance D1 en arrière-plan, via le Planificateur de tâches Windows."""
import csv
import json
import logging
import os
import sqlite3
from collections import deque
from contextlib import closing
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from time import sleep

import MetaTrader5 as mt5

import config as C
import notifications
import rapport
import robot
import tableau_de_bord

BASE = Path(__file__).resolve().parent
ETAT = BASE / "automatique_etat.json"
INTERVALLE = 60


def fenetre_entree(maintenant):
    debut = time.fromisoformat(os.getenv("HEURE_EXECUTION", "09:15"))
    fin = time.fromisoformat(os.getenv("HEURE_LIMITE", "21:00"))
    if debut >= fin:
        raise ValueError("HEURE_EXECUTION doit précéder HEURE_LIMITE.")
    local = maintenant.astimezone(rapport.DOUALA)
    return local.weekday() < 5 and debut <= local.time() < fin


def prochain_reveil(maintenant):
    local = maintenant.astimezone(rapport.DOUALA)
    debut = time.fromisoformat(os.getenv("HEURE_EXECUTION", "09:15"))
    reveil = datetime.combine(local.date(), debut, rapport.DOUALA)
    while reveil <= local or reveil.weekday() >= 5:
        reveil += timedelta(days=1)
    return reveil.isoformat()


def activite():
    try:
        with open(C.FICHIER_JOURNAL, encoding="utf-8", newline="") as fichier:
            lignes = deque(csv.DictReader(fichier, delimiter=";"), maxlen=18)
    except OSError:
        return []
    types = {"entrée": "trade", "sortie": "sortie", "veto": "veto", "refus taille": "signal"}
    return [
        {"heure": ligne.get("date_utc", ""), "courtier": ligne.get("courtier", ""),
         "type": types.get(ligne.get("action"), "info"),
         "titre": f"{ligne.get('symbole', '')} · {ligne.get('action', '')} · {ligne.get('resultat', '')}",
         "detail": ligne.get("raison", "")}
        for ligne in reversed(lignes)
    ]


class Planificateur:
    def __init__(self):
        with closing(sqlite3.connect(BASE / "automatique.sqlite3")) as connexion, connexion:
            connexion.execute("""
                CREATE TABLE IF NOT EXISTS passages (
                    serveur TEXT, compte INTEGER, symbole TEXT, bougie TEXT, mode TEXT,
                    PRIMARY KEY (serveur, compte, symbole, bougie, mode)
                )
            """)
            connexion.execute("CREATE TABLE IF NOT EXISTS messages (cle TEXT PRIMARY KEY)")
        self.rapports = []
        self.observations = {}
        self.demarrage_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        self.observations_fantomes = []
        self.fantome = None
        self.versions_fantomes = []
        if os.getenv("NKAP_FANTOME", "non").strip().lower() == "oui":
            if C.MODE != "TEST":
                raise ValueError("La collecte NKAP_FANTOME demande MODE=TEST.")
            from nkap.configuration import Parametres, charger_config
            from nkap.service.fantome import Fantome

            dossier = BASE / "observations_nkap"
            dossier.mkdir(exist_ok=True)
            self.fantome = Fantome(dossier / "fantome.sqlite3")
            _, champion, _ = charger_config(BASE / "config")
            autre = "er" if champion.regime == "ebsw" else "ebsw"
            self.versions_fantomes = [
                champion, Parametres.model_validate({**champion.model_dump(), "version": f"fantome-{autre}",
                                                    "regime": autre}),
            ]

    def observer(self, courtier, marche, bougies):
        if self.fantome is None:
            return
        donnees = bougies.sort_index()
        donnees.index = donnees.index.tz_localize("UTC")
        for p in self.versions_fantomes:
            self.observations_fantomes.append(
                self.fantome.observer(courtier.nom, marche, donnees, p, datetime.now(timezone.utc))
            )

    def entrees_permises(self):
        return fenetre_entree(datetime.now(timezone.utc))

    def nouveau(self, courtier, symbole, bougie, solde, positions):
        cle = (courtier.serveur.casefold(), courtier.login, symbole)
        observation = (bougie, solde, tuple(p.ticket for p in positions), self.entrees_permises())
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
        debut = rapport.debut_jour(maintenant)
        fin = maintenant + timedelta(seconds=1)
        transactions = mt5.history_deals_get(debut, fin)
        net, nombre = rapport.bilan(transactions, C.MAGIC)
        semaine, nombre_semaine = rapport.bilan(
            mt5.history_deals_get(rapport.debut_semaine(maintenant), fin), C.MAGIC
        )
        positions = courtier.positions()
        self.rapports.append({
            "courtier": courtier.nom,
            "devise": compte.currency,
            "capital": compte.equity,
            "positions": len(positions),
            "positions_detail": [
                {"symbole": p.symbol, "sens": "achat" if p.type == mt5.POSITION_TYPE_BUY else "vente",
                 "volume": p.volume, "prix": p.price_open, "stop": p.sl, "resultat": p.profit + p.swap}
                for p in positions
            ],
            "serveur": courtier.serveur,
            "levier": compte.leverage,
            "reel": courtier.est_compte_reel(),
            "ordres_autorises": robot.ordres_autorises(courtier)[0],
            "resultat": net,
            "transactions": nombre,
            "resultat_semaine": semaine,
            "transactions_semaine": nombre_semaine,
        })
        if not notifications.active():
            return
        identite = f"{courtier.serveur.casefold()}:{courtier.login}"
        if transactions is not None:
            identifiant = f"initialise:{identite}"
            deja_initialise = self.deja_envoye(identifiant)
            for deal in transactions:
                if deal.magic != C.MAGIC:
                    continue
                cle = f"deal:{identite}:{deal.ticket}"
                texte = (f"<b>{notifications.echapper(courtier.nom)} · {notifications.echapper(deal.symbol)}</b>\n"
                         f"Exécution MT5 #{deal.ticket} · net {rapport.montant_transaction(deal):+.2f} "
                         f"{notifications.echapper(compte.currency)}")
                if deja_initialise or deal.time_msc >= self.demarrage_ms:
                    self.notifier(cle, texte)
                else:
                    self.memoriser(cle)
            self.memoriser(identifiant)
        if net is not None and debut.weekday() < 5 and maintenant.astimezone(rapport.DOUALA).hour >= 21:
            self.notifier(f"jour:{identite}:{debut.date()}",
                          f"Bilan {notifications.echapper(courtier.nom)} du {debut:%d/%m} : "
                          f"{net:+.2f} {notifications.echapper(compte.currency)} ({nombre} exécutions).")
        if semaine is not None and debut.weekday() == 5 and maintenant.astimezone(rapport.DOUALA).hour >= 10:
            lundi = rapport.debut_semaine(maintenant)
            self.notifier(f"semaine:{identite}:{lundi.date()}",
                          f"Bilan de la semaine · {notifications.echapper(courtier.nom)} : "
                          f"{semaine:+.2f} {notifications.echapper(compte.currency)} "
                          f"({nombre_semaine} exécutions).")

    def deja_envoye(self, cle):
        with closing(sqlite3.connect(BASE / "automatique.sqlite3")) as connexion:
            return connexion.execute("SELECT 1 FROM messages WHERE cle = ?", (cle,)).fetchone() is not None

    def memoriser(self, cle):
        with closing(sqlite3.connect(BASE / "automatique.sqlite3")) as connexion, connexion:
            connexion.execute("INSERT OR IGNORE INTO messages VALUES (?)", (cle,))

    def notifier(self, cle, message):
        if not self.deja_envoye(cle) and notifications.envoyer(message):
            self.memoriser(cle)

    def publier(self, statut):
        etat = {"mode": C.MODE, "statut": statut, "heure": datetime.now(timezone.utc).isoformat(),
                "rapports": self.rapports}
        temporaire = ETAT.with_suffix(".tmp")
        temporaire.write_text(json.dumps(etat, ensure_ascii=False), encoding="utf-8")
        temporaire.replace(ETAT)
        tableau_de_bord.INSTANTANE = json.dumps({
            "nom": os.getenv("NOM_MASCOTTE", "Nkap"),
            "mode": C.MODE, "veto_claude": C.CLAUDE_ACTIF, "maj": etat["heure"],
            "message": statut, "humeur": "veille" if self.rapports else "erreur",
            "prochain_reveil": prochain_reveil(datetime.now(timezone.utc)),
            "compte_reel": any(r["reel"] for r in self.rapports),
            "ordres_autorises": any(r["ordres_autorises"] for r in self.rapports),
            "courtiers": {
                r["courtier"]: {**r, "connecte": True, "positions": r["positions_detail"],
                                "resultat_jour": r["resultat"], "trades_semaine": r["transactions_semaine"]}
                for r in self.rapports
            },
            "evenements": activite(),
            "fantome": self.observations_fantomes if self.fantome is not None else None,
        }, ensure_ascii=False)
        if self.fantome is not None:
            self.fantome.exporter(BASE / "observations_nkap" / "rapport.csv")
        dossier = BASE / "rapports_automatiques"
        dossier.mkdir(exist_ok=True)
        date = datetime.fromisoformat(etat["heure"]).astimezone(rapport.DOUALA).date()
        fichier = dossier / f"{date}.json"
        temporaire = fichier.with_suffix(".tmp")
        temporaire.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
        temporaire.replace(fichier)


def main():
    fenetre_entree(datetime.now(timezone.utc))
    robot.configurer_log()
    port = int(os.getenv("PORT_INTERFACE", "8765"))
    if not tableau_de_bord.demarrer(port):
        logging.getLogger("robot").error("Port local %s occupé. Nkap ne démarre pas.", port)
        raise SystemExit(1)
    planificateur = Planificateur()
    actifs = [conf for conf in C.COURTIERS if conf["actif"]]
    while True:
        planificateur.rapports.clear()
        planificateur.observations_fantomes.clear()
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
