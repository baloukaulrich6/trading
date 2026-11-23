"""Publie le dernier état par symbole dans le dossier partagé de MetaTrader."""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import MetaTrader5 as mt5

import config as C


def publier(login: int, symbole: str, message: str) -> None:
    terminal = mt5.terminal_info()
    if not login or terminal is None:
        return
    nom = "".join(c if c.isascii() and (c.isalnum() or c in "._-") else "_" for c in symbole)
    temporaire = None
    try:
        dossier = Path(terminal.commondata_path) / "Files" / "SuiviRobot"
        dossier.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=dossier, delete=False) as fichier:
            temporaire = Path(fichier.name)
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            fichier.write(f"{date} | Mode {C.MODE}\n{message}\n")
        os.replace(temporaire, dossier / f"{login}_{nom}.txt")
        temporaire = None
    except OSError as erreur:
        logging.getLogger("robot").warning("Suivi graphique indisponible : %s", erreur)
    finally:
        if temporaire is not None:
            try:
                temporaire.unlink(missing_ok=True)
            except OSError:
                pass
