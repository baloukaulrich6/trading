from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nkap.donnees.bougies import CacheBougies, charger_csv, resoudre, verifier
from nkap.indicateurs.calculs import efficiency_ratio, plus_haut


def bougies():
    dates = pd.date_range("2025-01-01", periods=3, tz="UTC")
    return pd.DataFrame({"open": [1, 2, 3], "high": [2, 3, 4], "low": [1, 2, 3],
                         "close": [2, 3, 4]}, index=dates)


def test_cache_et_dates_cloturees(tmp_path: Path):
    data = bougies().rename_axis("date_utc")
    chemin = tmp_path / "test.csv"
    data.to_csv(chemin)
    cutoff = datetime(2025, 1, 2, tzinfo=UTC)
    cache = CacheBougies(tmp_path / "cache.db")
    cache.ecrire("HFM", "EURUSDc", data)
    assert len(cache.lire("HFM", "EURUSDc", a_la_date=cutoff)) == 2
    assert len(charger_csv(chemin, a_la_date=cutoff)) == 2
    assert resoudre({"NAS100", "ustec"}, ["USTEC", "NAS100"]) == "ustec"


def test_validation_et_indicateurs():
    data = bougies()
    assert plus_haut(data["high"], 2).iloc[-1] == 3
    assert efficiency_ratio(data["close"], 2).iloc[-1] == 1
    assert efficiency_ratio(pd.Series([2, 2, 2]), 2).iloc[-1] == 0
    assert efficiency_ratio(pd.Series([2, 3, 2]), 2).iloc[-1] == 0
    data.iloc[0, data.columns.get_loc("high")] = 0
    with pytest.raises(ValueError, match="Prix"):
        verifier(data)
