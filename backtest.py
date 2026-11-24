"""Backtest des modules Turtles + contrarien sur l'historique journalier de MT5.

Résultats en « R » : 1R = la perte prévue si le stop est touché (1 % du capital).
L'écart (spread) actuel est déduit de chaque trade. Les swaps ne sont PAS comptés.
"""
import sys

import pandas as pd

import config as C
import strategie as S

COUPURE = pd.Timestamp("2020-01-01")   # avant : période de réglage, après : période de test


def simuler(d: pd.DataFrame, ecart: float) -> list[dict]:
    """Signal à la clôture, exécution à l'ouverture suivante, stop vérifié sur les plus hauts/bas."""
    trades, position, entree_prevue = [], None, None

    def clore(prix_sortie, date, motif):
        nonlocal position
        p = position
        gain = prix_sortie - p["entree"] if p["sens"] == "achat" else p["entree"] - prix_sortie
        trades.append({"date": p["date"], "sortie": date, "module": p["module"], "sens": p["sens"],
                       "R": (gain - ecart) / p["risque"], "motif": motif})
        position = None

    for i in range(len(d)):
        bougie = d.iloc[i]
        date = d.index[i]

        if position is not None and position["sortie_prevue"]:
            clore(bougie["open"], date, "règle de sortie")

        if position is None and entree_prevue is not None:
            sens, module, distance = entree_prevue
            entree = bougie["open"]
            stop = entree - distance if sens == "achat" else entree + distance
            position = {"date": date, "sens": sens, "module": module, "entree": entree,
                        "stop": stop, "risque": distance, "sortie_prevue": False}
            entree_prevue = None

        if position is not None:
            if position["sens"] == "achat" and bougie["low"] <= position["stop"]:
                clore(min(position["stop"], bougie["open"]), date, "stop")
            elif position["sens"] == "vente" and bougie["high"] >= position["stop"]:
                clore(max(position["stop"], bougie["open"]), date, "stop")

        if position is not None:
            if S.doit_sortir(bougie, position["sens"], position["module"]):
                position["sortie_prevue"] = True
        elif i + 1 < len(d):
            signal = S.signal_entree(bougie)
            if signal is not None:
                entree_prevue = (signal["sens"], signal["module"], C.STOP_EN_N * bougie["atr"])
    return trades


def statistiques(trades: list[dict], titre: str) -> None:
    if not trades:
        print(f"  {titre} : aucun trade")
        return
    r = pd.Series([t["R"] for t in trades])
    gains, pertes = r[r > 0].sum(), -r[r < 0].sum()
    facteur = gains / pertes if pertes > 0 else float("inf")

    capital = (1 + C.RISQUE_PAR_TRADE * r).cumprod()
    perte_max = (1 - capital / capital.cummax()).max()

    print(f"  {titre} : {len(r)} trades | gagnants {(r > 0).mean():.0%} | "
          f"facteur de profit {facteur:.2f} | résultat {capital.iloc[-1] - 1:+.1%} | "
          f"perte maximale {perte_max:.1%}")


def lancer(historiques: dict[str, tuple[pd.DataFrame, float]]) -> None:
    tous = []
    for symbole, (bougies, ecart) in historiques.items():
        trades = simuler(S.preparer(bougies), ecart)
        for t in trades:
            t["symbole"] = symbole
        tous += trades
        print(f"\n{symbole} ({bougies.index[0]:%Y} à {bougies.index[-1]:%Y}, écart {ecart})")
        for module in (S.TURTLES, S.CONTRARIEN):
            statistiques([t for t in trades if t["module"] == module], f"module {module}")

    tous.sort(key=lambda t: t["sortie"])
    print("\n=== Portefeuille complet ===")
    statistiques([t for t in tous if t["date"] < COUPURE], "Réglage (avant 2020)")
    statistiques([t for t in tous if t["date"] >= COUPURE], "Test (2020 et après)")
    pd.DataFrame(tous).to_csv("backtest_trades.csv", sep=";", index=False)
    print("\nDétail des trades : backtest_trades.csv")


def main() -> None:
    from courtier import Courtier
    from univers_marches import marches

    conf = next((c for c in C.COURTIERS if c["actif"]), None)
    if conf is None:
        sys.exit("Aucun courtier actif dans .env")

    courtier = Courtier(conf)
    courtier.connecter()
    try:
        historiques = {}
        for base in marches(courtier.nom):
            symbole = courtier.trouver_symbole(base)
            if symbole is None:
                print(f"{base} introuvable chez {courtier.nom}")
                continue
            info = courtier.info_symbole(symbole)
            historiques[symbole] = (courtier.bougies(symbole, 5000), info.spread * info.point)
    finally:
        courtier.deconnecter()
    lancer(historiques)


if __name__ == "__main__":
    main()
