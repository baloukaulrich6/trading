from pathlib import Path

import pytest
from pydantic import ValidationError

from nkap.configuration import Limites, Local, charger_config


def test_configuration_versionnee():
    univers, champion, limites = charger_config(Path("config"))
    assert univers.marches[0].alias["HFM"] == ["EURUSDc"]
    assert champion.entree_turtles == 20
    assert limites.risque_base == 0.01


def test_limites_et_secrets():
    _, _, limites = charger_config(Path("config"))
    with pytest.raises(ValidationError):
        Limites.model_validate({**limites.model_dump(), "risque_base": 0.03})
    assert "secret-de-test" not in repr(Local.model_validate({"cle_claude": "secret-de-test"}))
