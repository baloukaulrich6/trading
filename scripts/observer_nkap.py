"""Observe les bougies HFM dans la nouvelle architecture, sans aucun envoi."""
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import sleep

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import config as C
from courtier import Courtier
from nkap.configuration import Parametres, charger_config
from nkap.service.fantome import Fantome


def passage(courtier: Courtier, fantome: Fantome, versions: list[Parametres], marches: list[str]) -> int:
    courtier.connecter()
    try:
        maintenant = datetime.now(UTC)
        reussis = 0
        for marche in marches:
            symbole = courtier.trouver_symbole(marche)
            if symbole is None:
                print(f"{marche} : indisponible", flush=True)
                continue
            try:
                bougies = courtier.bougies(symbole, 400).sort_index()
                bougies.index = bougies.index.tz_localize("UTC")
                observations = [fantome.observer(courtier.nom, marche, bougies, p, maintenant)
                                for p in versions]
                print(json.dumps(observations, ensure_ascii=False), flush=True)
                reussis += 1
            except ValueError as erreur:
                print(f"{symbole} : {erreur}", flush=True)
        return reussis
    finally:
        courtier.deconnecter()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--continu", action="store_true")
    parser.add_argument("--dossier", type=Path, default=BASE / "observations_nkap")
    args = parser.parse_args()
    args.dossier.mkdir(parents=True, exist_ok=True)
    fantome = Fantome(args.dossier / "fantome.sqlite3")
    _, champion, _ = charger_config(BASE / "config")
    autre = "er" if champion.regime == "ebsw" else "ebsw"
    challenger = Parametres.model_validate({**champion.model_dump(), "version": f"fantome-{autre}",
                                          "regime": autre})
    hfm = next(conf for conf in C.COURTIERS if conf["nom"] == "HFM")
    try:
        while True:
            nombre = 0
            try:
                nombre = passage(Courtier(hfm), fantome, [champion, challenger], C.SYMBOLES)
            except (OSError, RuntimeError, ValueError) as erreur:
                print(f"HFM indisponible : {erreur}", flush=True)
            fantome.exporter(args.dossier / "rapport.csv")
            if not args.continu:
                return 0 if nombre else 1
            sleep(60)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
