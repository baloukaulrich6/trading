"""Robot principal : à lancer une fois par jour, après la clôture des bougies journalières.

MODE=TEST   : calcule les signaux sans envoyer d'ordre.
MODE=ORDRES : envoie les ordres sur le compte configuré (démo d'abord !).
"""
import csv
import logging
import os
import sys
from datetime import datetime, timezone

import config as C
import risque as R
import strategie as S
from courtier import Courtier
from univers_marches import marches
from suivi_mt5 import publier

log = logging.getLogger("robot")

CHAMPS_JOURNAL = ["date_utc", "mode", "courtier", "symbole", "action", "sens", "module",
                  "volume", "prix", "stop", "resultat", "raison"]


def configurer_log() -> None:
    log.setLevel(logging.INFO)
    format_log = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    gestionnaires = [logging.FileHandler(C.FICHIER_LOG, encoding="utf-8")]
    if sys.stdout is not None:
        gestionnaires.append(logging.StreamHandler(sys.stdout))
    for gestionnaire in gestionnaires:
        gestionnaire.setFormatter(format_log)
        log.addHandler(gestionnaire)


def journaliser(**champs) -> None:
    nouveau = not os.path.exists(C.FICHIER_JOURNAL)
    champs.setdefault("date_utc", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    champs.setdefault("mode", C.MODE)
    with open(C.FICHIER_JOURNAL, "a", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=CHAMPS_JOURNAL, delimiter=";")
        if nouveau:
            ecrivain.writeheader()
        ecrivain.writerow({k: champs.get(k, "") for k in CHAMPS_JOURNAL})


def ordres_autorises(c: Courtier) -> tuple[bool, str]:
    if C.MODE != "ORDRES":
        return False, "mode TEST : aucun ordre envoyé"
    if c.est_compte_reel() and not c.reel_autorise():
        return False, "compte RÉEL sans confirmation : aucun ordre envoyé"
    return True, "ok"


def gerer_sorties(c: Courtier, symbole: str, ligne, envoyer: bool, motif: str) -> list[str]:
    sorties = []
    for p in c.positions(symbole):
        sens = "achat" if p.type == 0 else "vente"
        module = p.comment[:3] if p.comment[:3] in (S.TURTLES, S.CONTRARIEN) else S.TURTLES
        if not S.doit_sortir(ligne, sens, module):
            continue
        ok, detail = c.fermer(p) if envoyer else (False, motif)
        log.info("%s %s : sortie %s %s -> %s", c.nom, symbole, module, sens, detail)
        sorties.append(detail)
        journaliser(courtier=c.nom, symbole=symbole, action="sortie", sens=sens, module=module,
                    volume=p.volume, prix=ligne["close"], resultat="ok" if ok else "non envoyé",
                    raison=detail)
    return sorties


def chercher_entree(c: Courtier, symbole: str, ligne, capital: float, envoyer: bool,
                    motif: str, planificateur=None) -> bool:
    signal = S.signal_entree(ligne)
    if signal is None:
        return False

    sens, module = signal["sens"], signal["module"]
    prix = c.prix_actuel(symbole, sens)
    distance = C.STOP_EN_N * ligne["atr"]
    stop = prix - distance if sens == "achat" else prix + distance

    info = c.info_symbole(symbole)
    base_journal = dict(courtier=c.nom, symbole=symbole, sens=sens, module=module,
                        prix=round(prix, info.digits), stop=round(stop, info.digits))
    try:
        perte_min, marge_min = c.cout_ordre(symbole, sens, info.volume_min, prix, base_journal["stop"])
        compte = c.infos_compte()
        if marge_min > compte.margin_free:
            volume, motif_taille = 0.0, f"marge minimale trop élevée ({marge_min:.2f} {compte.currency})"
        else:
            volume, motif_taille = R.taille_position(
                capital, distance, info, perte_par_lot=perte_min / info.volume_min
            )
    except ValueError as erreur:
        volume, motif_taille = 0.0, str(erreur)
    if volume == 0:
        publier(c.login, symbole, f"Signal {sens} · {motif_taille}")
        log.info("%s %s : signal %s ignoré (%s)", c.nom, symbole, module, motif_taille)
        journaliser(**base_journal, action="refus taille", resultat="ignoré", raison=motif_taille)
        return False
    if planificateur is not None and not planificateur.reserver(c, symbole, ligne.name):
        return False

    if envoyer and planificateur is not None:
        objectif = planificateur.objectif_compte(c, c.infos_compte())
        if objectif and objectif["bloque"]:
            publier(c.login, symbole, objectif["motif"])
            journaliser(**base_journal, volume=volume, action="objectif",
                        resultat="non envoyé", raison=objectif["motif"])
            return False

    ok, detail = c.ouvrir(symbole, sens, volume, stop, module) if envoyer else (False, motif)
    publier(c.login, symbole, f"Signal {sens} · {detail}")
    log.info("%s %s : entrée %s %s %.2f lot -> %s", c.nom, symbole, module, sens, volume, detail)
    journaliser(**base_journal, volume=volume, action="entrée",
                resultat="ok" if ok else "non envoyé", raison=f"{signal['raison']} | {detail}")
    return ok


def traiter_courtier(conf: dict, planificateur=None) -> None:
    c = Courtier(conf)
    c.connecter()
    try:
        compte = c.infos_compte()
        capital = compte.equity
        log.info("%s : capital %.2f %s, levier 1:%s", c.nom, capital, compte.currency,
                 compte.leverage)

        envoyer, motif = ordres_autorises(c)
        analyse_seule = C.MODE == "TEST" and capital <= 0
        cle_risque = f"{c.nom}-DEMO:{c.login}" if c.demo_uniquement else c.nom
        bloque, motif_arret = R.arret_urgence(cle_risque, capital)
        if bloque:
            log.warning("%s : nouveaux trades bloqués (%s)", c.nom, motif_arret)
        objectif = planificateur.objectif_compte(c, compte) if planificateur is not None else None
        if objectif and objectif["bloque"]:
            log.info("%s : %s", c.nom, objectif["motif"])
        nb_positions = len(c.positions())

        for base in marches(c.nom):
            symbole = c.trouver_symbole(base)
            if symbole is None:
                log.warning("%s : symbole %s introuvable", c.nom, base)
                if planificateur is not None:
                    planificateur.noter_marche(c, base, None, None)
                continue

            if planificateur is not None:
                if planificateur.fantome is not None and C.MODE == "TEST":
                    bougies_fantome = c.bougies(symbole, 400)
                    planificateur.observer(c, base, bougies_fantome)
                    planificateur.noter_marche(c, base, symbole, None, fantome=True, donnees=bougies_fantome)
                    continue
                bougie = c.bougies(symbole, 1).index[-1]
                positions = c.positions(symbole)
                if C.MODE == "ORDRES" and capital <= 0 and not positions:
                    publier(c.login, symbole, "En attente de fonds")
                    continue
                if not planificateur.nouveau(c, symbole, bougie, compte.balance, positions):
                    continue
            donnees = S.preparer(c.bougies(symbole, 400))
            ligne = donnees.iloc[-1]
            if planificateur is not None and ligne.name != bougie:
                continue
            if planificateur is not None:
                planificateur.noter_marche(c, base, symbole, ligne, donnees=donnees)
            log.info("%s %s : clôture %s, régime %s (EBSW %.2f), RSI %.1f", c.nom, symbole,
                     ligne["close"], ligne["regime"], ligne["ebsw"], ligne["rsi"])

            if analyse_seule:
                signal = S.signal_entree(ligne)
                if signal is None:
                    log.info("%s %s : aucun signal d'entrée", c.nom, symbole)
                    publier(c.login, symbole, "Aucun signal d'entrée")
                else:
                    log.info("%s %s : signal %s %s (%s), stop indicatif %s",
                             c.nom, symbole, signal["sens"], signal["module"],
                             signal["raison"], signal["stop"])
                    publier(c.login, symbole, f"Signal {signal['sens']} · {signal['raison']}")
                continue

            positions = c.positions_symbole(symbole)
            if positions:
                if planificateur is not None and not planificateur.reserver(c, symbole, ligne.name):
                    continue
                sorties = gerer_sorties(c, symbole, ligne, envoyer, motif)
                publier(c.login, symbole, " | ".join(sorties) or "Position existante sur le symbole")
                continue
            if bloque or nb_positions >= C.MAX_POSITIONS:
                publier(c.login, symbole, motif_arret if bloque else "Limite de positions atteinte")
                continue
            if objectif and objectif["bloque"]:
                publier(c.login, symbole, objectif["motif"])
                continue
            if planificateur is not None and not planificateur.entrees_permises():
                publier(c.login, symbole, "En attente de la fenêtre d'entrée (heure de Douala)")
                continue
            publier(c.login, symbole, f"Clôture {ligne['close']} · {ligne['regime']} · RSI {ligne['rsi']:.1f}")
            if chercher_entree(c, symbole, ligne, capital, envoyer, motif, planificateur):
                nb_positions += 1
        if planificateur is not None:
            planificateur.relever(c, c.infos_compte() or compte)
    finally:
        c.deconnecter()


def main() -> None:
    configurer_log()
    log.info("===== Démarrage du robot, mode %s =====", C.MODE)
    for conf in C.COURTIERS:
        if not conf["actif"]:
            continue
        try:
            traiter_courtier(conf)
        except Exception as erreur:
            log.exception("%s : erreur %s", conf["nom"], erreur)
    log.info("===== Fin =====")


if __name__ == "__main__":
    main()
