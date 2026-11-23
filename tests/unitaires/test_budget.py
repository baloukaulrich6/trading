from datetime import UTC, datetime
from unittest.mock import Mock

from nkap.claude.budget import Budget
from nkap.claude.client import ClientVeto
from nkap.domaine.modeles import Ordre, Signal


def test_budget_veto_et_timeout(tmp_path):
    maintenant = datetime(2025, 1, 1, tzinfo=UTC)
    ordre = Ordre("id", Signal("EURUSD", maintenant, "vente", "TUR", 1), 1, 10, 11)
    budget = Budget(tmp_path / "couts.db", 50)
    transport = Mock(return_value=('{"decision":"autoriser","raison":"Calendrier vérifié"}', 5))
    client = ClientVeto(budget, transport, lambda: maintenant, 25)
    assert client(ordre).autorisee
    transport.return_value = ("illisible", 5)
    assert not client(ordre).autorisee
    transport.side_effect = TimeoutError
    assert "indisponible" in client(ordre).raison
    assert "Budget" in client(ordre).raison
    assert transport.call_count == 3
    assert budget.reserver("nouveau-mois", maintenant.replace(month=2), 25)
