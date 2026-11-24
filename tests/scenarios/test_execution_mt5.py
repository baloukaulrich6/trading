from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

from nkap.configuration import Local, charger_config
from nkap.domaine.modeles import Ordre, Signal
from nkap.execution.mt5 import CourtierMT5, reference
from nkap.execution.ordres import Executeur, Validation
from nkap.risque.limites import EtatRisque


def test_mt5_precontrole_risque_identifiant_et_stop(tmp_path):
    _, _, limites = charger_config(Path("config"))
    api = Mock()
    api.ACCOUNT_TRADE_MODE_DEMO, api.ACCOUNT_TRADE_MODE_REAL = 0, 2
    api.account_info.return_value = NS(server="HFM-Demo", login=1, trade_mode=0, margin_free=500, equity=1000)
    api.positions_get.return_value = ()
    api.orders_get.return_value = ()
    api.symbol_info.return_value = NS(digits=5, filling_mode=2)
    api.symbol_info_tick.return_value = NS(bid=1.11, ask=1.11002)
    api.order_calc_profit.return_value = -12
    api.order_calc_margin.return_value = 10
    api.order_check.return_value = NS(retcode=0)
    api.order_send.return_value = NS(retcode=api.TRADE_RETCODE_DONE, deal=19, order=29)
    courtier = CourtierMT5(api, {"EURUSD": "EURUSDc"}, 7, limites,
                         lambda: EtatRisque(1000, 1000, 1000, 0), lambda ordre: ())
    moteur = Executeur(tmp_path / "mt5.db", courtier)
    ordre = Ordre("D1-1", Signal("EURUSD", datetime(2026, 1, 1, tzinfo=UTC), "achat", "SMC", .01),
                  .01, 1.11, 1.10)
    assert moteur.executer(ordre, "hfm-demo:1", Local(mode="DEMO"), Validation()).etat == "refuse"
    api.order_send.assert_not_called()
    api.order_calc_profit.return_value = -8
    assert moteur.executer(ordre, "hfm-demo:1", Local(mode="DEMO"), Validation()).ticket == "19"
    demande = api.order_send.call_args.args[0]
    assert demande["sl"] == 1.10 and demande["comment"] == reference("D1-1")
    assert moteur.executer(ordre, "hfm-demo:1", Local(mode="DEMO"), Validation()).etat == "refuse"
    api.order_send.assert_called_once()
    api.positions_get.return_value = [NS(magic=7, ticket=2, symbol="EURUSDc",
                                         type=api.POSITION_TYPE_BUY, sl=1.10, tp=1.15)]
    assert not courtier.resserrer_stop(2, 1.09)
    assert courtier.resserrer_stop(2, 1.105)
    assert api.order_send.call_args.args[0]["tp"] == 1.15
