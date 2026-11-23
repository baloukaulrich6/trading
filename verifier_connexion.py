"""Diagnostic : vérifie la connexion à chaque courtier actif et ce que le robot pourra trader.

À lancer AVANT le robot : python verifier_connexion.py
Aucun ordre n'est envoyé.
"""
import config as C
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
        print(f"Marge libre {compte.margin_free:.2f} {compte.currency} | "
              f"Budget au stop {compte.equity * C.RISQUE_PAR_TRADE:.2f} {compte.currency}")

        for base in C.SYMBOLES:
            symbole = c.trouver_symbole(base)
            if symbole is None:
                print(f"- {base} : introuvable chez ce courtier")
                continue
            info = c.info_symbole(symbole)
            ligne = S.preparer(c.bougies(symbole, 400)).iloc[-1]
            distance = C.STOP_EN_N * ligne["atr"]
            signal = S.signal_entree(ligne)
            print(f"- {symbole} | lot minimal {info.volume_min} | "
                  f"signal : {signal['sens'] if signal else 'aucun'}")
            for sens in ("achat", "vente"):
                try:
                    prix = c.prix_actuel(symbole, sens)
                    stop = round(prix - distance if sens == "achat" else prix + distance, info.digits)
                    risque, marge = c.cout_ordre(symbole, sens, info.volume_min, prix, stop)
                    limites = []
                    if risque > compte.equity * C.RISQUE_PAR_TRADE:
                        limites.append("risque trop élevé")
                    if marge > compte.margin_free:
                        limites.append("marge insuffisante")
                    resultat = ", ".join(limites) or "lot minimal compatible"
                    print(f"  {sens} : risque {risque:.2f} {compte.currency} | "
                          f"marge {marge:.2f} {compte.currency} | {resultat}")
                except ValueError as erreur:
                    print(f"  {sens} : {erreur}")
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
