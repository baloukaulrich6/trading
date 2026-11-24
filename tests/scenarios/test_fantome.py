import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import pytest

from nkap.configuration import Parametres, charger_config
from nkap.service.fantome import Fantome, resultat_au_stop


def test_observation_sans_rejeu_ni_entree_retroactive(tmp_path):
    _, champion, _ = charger_config(Path("config"))
    params = Parametres.model_validate({**champion.model_dump(), "regime": "er",
                                        "entree_turtles": 2, "periode_er": 2})
    dates = pd.date_range("2026-01-01", periods=8, tz="UTC")
    valeurs = list(range(10, 18))
    d = pd.DataFrame({"open": valeurs, "high": [a + .5 for a in valeurs],
                      "low": [a - .5 for a in valeurs], "close": valeurs}, index=dates)
    base = tmp_path / "fantome.db"
    observer = Fantome(base)
    premiere_lecture = dates[3] + pd.Timedelta(hours=8)
    assert observer.observer("HFM", "EURUSD", d.iloc[:3], params, premiere_lecture)["signal"] == "achat"
    observer.observer("HFM", "EURUSD", d.iloc[:3], params, premiere_lecture)
    observer.observer("HFM", "EURUSD", d, params, dates[-1] + pd.Timedelta(days=1))
    with closing(sqlite3.connect(base)) as db:
        assert db.execute("SELECT COUNT(*) FROM observations").fetchone() == (2,)
        entree, = db.execute("SELECT entree FROM resultats WHERE horizon=1").fetchone()
        assert entree == d.iloc[4]["open"]
        assert db.execute("SELECT COUNT(*) FROM resultats WHERE horizon=5").fetchone() == (0,)
    with pytest.raises(ValueError, match="future"):
        observer.observer("HFM", "EURUSD", d, params, dates[3])


def test_gap_en_fantome():
    d = pd.DataFrame({"open": [10, 7], "low": [9.5, 6], "high": [11, 8], "close": [10.5, 7.5]})
    assert resultat_au_stop(d, "achat", 2) == (10, 7, -1.5)
