"""Exporte les bougies MT5 clôturées sans jamais demander d'ordre."""
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import MetaTrader5 as mt5

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import config as C
from courtier import Courtier
from nkap.configuration import charger_config


def exporter(nom: str, barres: int, dossier: Path) -> int:
    conf = next((c for c in C.COURTIERS if c["nom"].casefold() == nom.casefold()), None)
    if conf is None:
        raise ValueError("Courtier inconnu.")
    marches, _, _ = charger_config(BASE / "config")
    courtier = Courtier(conf)
    courtier.connecter()
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        maintenant = datetime.now(UTC)
        bilan = []
        for marche in marches.marches:
            alias = marche.alias.get(courtier.nom, [])
            symbole = next((a for a in alias if mt5.symbol_info(a) is not None), None)
            if symbole is None or not mt5.symbol_select(symbole, True):
                print(f"{marche.symbole} : absent chez {courtier.nom}")
                continue
            try:
                donnees = courtier.bougies(symbole, barres).sort_index()
            except ValueError as erreur:
                print(f"{symbole} : {erreur}")
                continue
            donnees.index = donnees.index.tz_localize("UTC")
            fichier = dossier / f"{courtier.nom}-{marche.symbole}-{maintenant:%Y%m%dT%H%M%S}.csv"
            donnees.to_csv(fichier, index_label="date_utc")
            bilan.append({"marche": marche.symbole, "symbole": symbole, "bougies": len(donnees),
                          "premiere_bougie": donnees.index[0].isoformat(),
                          "derniere_bougie": donnees.index[-1].isoformat(), "csv": fichier.name})
            print(f"{fichier.name} : {len(donnees)} bougies")
        manifeste = dossier / f"{courtier.nom}-{maintenant:%Y%m%dT%H%M%S}-export.json"
        manifeste.write_text(json.dumps({"source": courtier.nom, "export_utc": maintenant.isoformat(),
                                         "marches": bilan}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if bilan else 1
    finally:
        courtier.deconnecter()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--courtier", default="HFM")
    parser.add_argument("--barres", type=int, default=3000)
    parser.add_argument("--dossier", type=Path, default=Path("exports_d1"))
    args = parser.parse_args()
    if args.barres <= 0:
        parser.error("--barres doit être positif.")
    try:
        return exporter(args.courtier, args.barres, args.dossier)
    except (OSError, ValueError) as erreur:
        parser.error(str(erreur))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
