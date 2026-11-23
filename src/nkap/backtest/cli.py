"""Commande de recherche reproductible avec paramètres et coûts explicites."""
import argparse
import json
from dataclasses import asdict
from datetime import datetime
from math import isfinite
from pathlib import Path

from nkap.backtest.moteur import Couts
from nkap.backtest.walk_forward import verifier_reserve, walk_forward
from nkap.configuration import charger_config
from nkap.donnees.bougies import charger_csv


def compatible_json(valeur: object) -> object:
    if isinstance(valeur, float) and not isfinite(valeur):
        return "infini" if valeur > 0 else None
    if isinstance(valeur, dict):
        return {cle: compatible_json(v) for cle, v in valeur.items()}
    if isinstance(valeur, (tuple, list)):
        return [compatible_json(v) for v in valeur]
    return valeur


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--marche", required=True)
    parser.add_argument("--a-la-date", required=True, help="Horodatage ISO avec décalage de fuseau")
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--capital", type=float, required=True, help="Capital simulé en USD")
    parser.add_argument("--spread", type=float, required=True, help="Spread aller-retour, en unités de prix")
    parser.add_argument("--glissement", type=float, required=True, help="Par exécution, en unités de prix")
    parser.add_argument("--commission", type=float, required=True, help="USD par lot et par aller-retour")
    parser.add_argument("--swap", type=float, required=True, help="Hypothèse USD par lot et par nuit")
    parser.add_argument("--valeur-unite-lot", type=float, required=True, help="USD par unité de prix et par lot")
    parser.add_argument("--lot-min", type=float, required=True)
    parser.add_argument("--pas", type=float, required=True)
    parser.add_argument("--claude-par-signal", type=float, default=0.0, help="Hypothèse USD, sans appel API")
    parser.add_argument("--reserve", action="store_true", help="Évalue le champion configuré sur la réserve")
    args = parser.parse_args()
    try:
        univers, champion, limites = charger_config(args.config)
        if args.marche not in {m.symbole for m in univers.marches}:
            raise ValueError("Marché absent de config/marches.yaml.")
        data = charger_csv(args.csv, a_la_date=datetime.fromisoformat(args.a_la_date))
        couts = Couts(args.spread, args.glissement, args.commission, args.swap, args.valeur_unite_lot,
                     args.lot_min, args.pas, args.claude_par_signal)
        evaluation = walk_forward(args.marche, data, champion, limites, couts, args.capital)
        rapport = asdict(evaluation)
        rapport["admission_reel"] = False
        rapport["comparaison"] = "Règles seules, EBSW contre ER en formation, aucun appel API"
        rapport["comparaison_filtre_analyste"] = asdict(walk_forward(
            args.marche, data, champion, limites, couts, args.capital, avec_agents=True
        ))
        if args.reserve:
            rapport["reserve"] = asdict(verifier_reserve(
                args.marche, data, champion, limites, couts, args.capital, evaluation
            ))
        print(json.dumps(compatible_json(rapport), ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if not evaluation.refus else 1
    except (OSError, ValueError) as erreur:
        parser.error(str(erreur))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
