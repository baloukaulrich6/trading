"""Diagnostic : vérifie la connexion à chaque courtier actif et ce que le robot pourra trader.

À lancer AVANT le robot : python verifier_connexion.py
Aucun ordre n'est envoyé.
"""
import config as C
import risque as R
import strategie as S
from courtier import Courtier


def verifier(conf: dict) -> None:
    print(f"\n===== {conf['nom']} =====")
    c = Courtier(conf)
    c.connecter()
    try:
        compte = c.infos_compte()
        print(f"Compte {compte.login} | serveur {c.serveur} | "
              f"{'RÉEL' if c.est_compte_reel() else 'démo'}")
        print(f"Capital {compte.equity:.2f} {compte.currency} | levier 1:{compte.leverage}")
        if compte.leverage > 100:
            print("  Conseil : baisse l'effet de levier à 1:100 dans l'espace client.")

        for base in C.SYMBOLES:
            symbole = c.trouver_symbole(base)
            if symbole is None:
                print(f"- {base} : introuvable chez ce courtier")
                continue
            info = c.info_symbole(symbole)
            ligne = S.preparer(c.bougies(symbole, 400)).iloc[-1]
            distance = C.STOP_EN_N * ligne["atr"]
            volume, motif = R.taille_position(compte.equity, distance, info)
            print(f"- {base} -> {symbole} | écart {info.spread} points | lot mini {info.volume_min} "
                  f"| stop 2N = {distance:.{info.digits}f} | taille à 1 % : "
                  f"{volume if volume else 'IMPOSSIBLE'} ({motif})")
    finally:
        c.deconnecter()


if __name__ == "__main__":
    actifs = [conf for conf in C.COURTIERS if conf["actif"]]
    if not actifs:
        print("Aucun courtier actif : vérifie EXNESS_ACTIF / HFM_ACTIF dans .env")
    for conf in actifs:
        try:
            verifier(conf)
        except Exception as erreur:
            print(f"{conf['nom']} : ERREUR -> {erreur}")
