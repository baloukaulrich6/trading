from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from nkap.claude.budget import Budget
from nkap.claude.superviseur import superviser


def test_supervision_read_only(tmp_path):
    budget = Budget(tmp_path / "claude.db", 25)
    transport = Mock(return_value=('{"resume":"Données rares","post_mortem":[],"alertes":[]}', 5))
    maintenant = datetime(2026, 1, 1, tzinfo=UTC)
    revue = superviser({"trades": 1}, budget, maintenant, transport, 20)
    assert revue.resume == "Données rares"
    transport.return_value = ('{"resume":"x","post_mortem":[],"alertes":[],"ordre":"achat"}', 5)
    with pytest.raises(ValueError, match="non conforme"):
        superviser({"trades": 1}, budget, maintenant, transport, 20)
    with pytest.raises(ValueError, match="Budget"):
        superviser({"trades": 1}, budget, maintenant, transport, 20)
    assert transport.call_count == 2
