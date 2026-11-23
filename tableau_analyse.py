"""Rapport HTML en lecture seule à partir des dernières bougies D1 clôturées."""
import argparse
from datetime import datetime, timezone
from html import escape
from math import ceil, isfinite
from pathlib import Path

import config as C
import risque as R
import strategie as S
from courtier import Courtier
from univers_marches import marches


STYLE = """
:root { color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif;
        background: #101821; color: #e9f0f7; }
body { margin: 0 auto; padding: 2rem 1rem; max-width: 90rem; }
h1 { font-size: clamp(1.8rem, 4vw, 3rem); margin: 0 0 .5rem; }
h2 { margin: 0 0 .5rem; }
p { color: #b6c7d6; line-height: 1.55; }
section { background: #172430; border: 1px solid #334959; border-radius: 1rem;
          padding: 1.25rem; margin: 1.5rem 0; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: .75rem; text-align: left; border-bottom: 1px solid #334959; }
th { color: #a7e6d3; background: #1c3040; }
tbody tr:hover { background: #203545; }
"""


def capital_positif(valeur: str) -> float:
    try:
        montant = float(valeur.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError("Saisis un montant numérique.") from None
    if not isfinite(montant) or montant <= 0:
        raise argparse.ArgumentTypeError("Le montant doit être supérieur à zéro.")
    return montant


def montant_usd(montant: float) -> str:
    return f"{montant:,.2f} USD".replace(",", " ").replace(".", ",")


def ligne_html(valeurs, balise="td") -> str:
    cellules = "".join(f"<{balise}>{escape(str(v))}</{balise}>" for v in valeurs)
    return f"<tr>{cellules}</tr>"


def analyser_marche(courtier, base, facteur, scenarios):
    symbole = courtier.trouver_symbole(base)
    if symbole is None:
        raise ValueError("Symbole introuvable chez ce courtier")
    info = courtier.info_symbole(symbole)
    if info is None:
        raise ValueError("Caractéristiques du symbole indisponibles")
    ligne = S.preparer(courtier.bougies(symbole, 400)).iloc[-1]
    signal = S.signal_entree(ligne)
    signal_texte = f"{signal['sens']} · {signal['raison']}" if signal else "Aucun signal"
    stop = f"{signal['stop']:.{info.digits}f}" if signal else "—"

    valeurs = (
        symbole, ligne.name.strftime("%Y-%m-%d"), f"{ligne['close']:.{info.digits}f}",
        ligne["regime"], f"{ligne['rsi']:.1f}", signal_texte, stop, f"{info.volume_min:g}",
    )
    distance = C.STOP_EN_N * ligne["atr"]
    donnees_risque = (distance, info.trade_tick_size, info.trade_tick_value,
                      info.volume_min, info.volume_max, info.volume_step)
    if facteur is None or not all(isfinite(v) and v > 0 for v in donnees_risque):
        return (*valeurs, "Indisponible", "Indisponible", *("—" for _ in scenarios))

    perte_min = distance / info.trade_tick_size * info.trade_tick_value * info.volume_min
    capital_min = perte_min / C.RISQUE_PAR_TRADE / facteur
    # Arrondir le seuil vers le haut pour éviter d'afficher un capital insuffisant.
    capital_min = ceil(capital_min * 100) / 100
    volumes = []
    for capital in scenarios:
        volume, _ = R.taille_position(capital * facteur, distance, info)
        volumes.append(f"{volume:g} lot" if volume > 0 else "Insuffisant")
    return (*valeurs, montant_usd(perte_min / facteur), montant_usd(capital_min), *volumes)


def colonnes_analyse(scenarios):
    return (
        "Symbole MT5", "Bougie D1", "Clôture", "Régime", "RSI 2 j", "Signal", "Stop indicatif",
        "Lot minimal", "Perte au stop (lot min.)", f"Capital min. à {C.RISQUE_PAR_TRADE:.0%}",
        *(montant_usd(montant) for montant in scenarios),
    )


def relever_courtier(conf, scenarios):
    courtier = Courtier(conf)
    courtier.connecter()
    try:
        compte = courtier.infos_compte()
        if compte is None:
            raise ValueError("Informations du compte indisponibles")
        facteur = {"USD": 1, "USC": 100}.get(compte.currency.upper())
        resume = f"Capital réel : {compte.equity:.2f} {compte.currency}"
        if facteur == 100:
            resume += f" ({montant_usd(compte.equity / facteur)})"
        if facteur is None:
            resume += " · Simulation USD indisponible pour cette devise."
        lignes = []
        for base in marches(courtier.nom):
            try:
                lignes.append(analyser_marche(courtier, base, facteur, scenarios))
            except (RuntimeError, ValueError) as erreur:
                lignes.append((base, "—", "—", "—", "—", str(erreur)))
        return resume, lignes
    finally:
        courtier.deconnecter()


def section_courtier(conf, scenarios) -> str:
    resume, lignes = relever_courtier(conf, scenarios)
    colonnes = colonnes_analyse(scenarios)
    corps = "".join(ligne_html((*ligne, *("" for _ in range(len(colonnes) - len(ligne)))))
                    for ligne in lignes)
    return (
        f"<section><h2>{escape(conf['nom'])}</h2><p>{escape(resume)}</p>"
        f"<div class='scroll'><table><thead>{ligne_html(colonnes, 'th')}</thead>"
        f"<tbody>{corps}</tbody></table></div></section>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital", nargs="+", type=capital_positif, default=[25, 50, 100, 200],
                        metavar="USD", help="Capitaux fictifs en dollars à comparer")
    args = parser.parse_args()
    sections = []
    succes = 0
    for conf in C.COURTIERS:
        if conf["actif"]:
            try:
                sections.append(section_courtier(conf, args.capital))
                succes += 1
            except (RuntimeError, ValueError, ConnectionError) as erreur:
                sections.append(f"<section><h2>{escape(conf['nom'])}</h2>"
                                f"<p>Analyse indisponible : {escape(str(erreur))}</p></section>")
    if not sections:
        parser.error("Active HFM_ACTIF ou EXNESS_ACTIF dans .env.")

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fichier = Path("tableau_analyse.html")
    fichier.write_text(
        f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analyse du robot MT5</title><style>{STYLE}</style></head>
<body><main><h1>Analyse du robot MT5</h1>
<p>Calcul du {date} · Dernières bougies journalières clôturées · Aucun ordre</p>
{''.join(sections)}
<p>Les colonnes en USD comparent des capitaux fictifs. Le capital minimal est estimé
à partir de la distance du stop ({C.STOP_EN_N:g} ATR), du risque par position ({C.RISQUE_PAR_TRADE:.0%})
et des caractéristiques MT5 du symbole. Ce seuil ne tient pas compte de la marge, des frais,
du glissement ni des conditions de dépôt du courtier.</p>
</main></body></html>""", encoding="utf-8",
    )
    print(f"Rapport : {fichier.resolve()}")
    return 0 if succes else 1


if __name__ == "__main__":
    raise SystemExit(main())
