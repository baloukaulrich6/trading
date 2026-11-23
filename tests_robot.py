"""Tests du robot SANS MetaTrader : un faux MT5 avec des prix inventés remplace le vrai.

Lancer : python tests_robot.py
Chaque test affiche OK ou s'arrête sur une erreur.
"""
import os
import sys
import tempfile
import types

import numpy as np
import pandas as pd

# ---------- Faux module MetaTrader5 (injecté avant d'importer le robot) ----------
faux = types.ModuleType("MetaTrader5")
faux.TIMEFRAME_D1 = 16408
faux.ORDER_TYPE_BUY, faux.ORDER_TYPE_SELL = 0, 1
faux.POSITION_TYPE_BUY = 0
faux.ORDER_FILLING_FOK, faux.ORDER_FILLING_IOC, faux.ORDER_FILLING_RETURN = 0, 1, 2
faux.TRADE_ACTION_DEAL, faux.ORDER_TIME_GTC, faux.TRADE_RETCODE_DONE = 1, 0, 10009
faux.ENVOIS = []

_hasard = np.random.default_rng(7)


def _serie(n, depart, vol):
    rendements = _hasard.normal(0.0002, vol, n)
    cloture = depart * np.exp(np.cumsum(rendements))
    ouverture = np.r_[cloture[0], cloture[:-1]]
    haut = np.maximum(ouverture, cloture) * (1 + np.abs(_hasard.normal(0, vol / 2, n)))
    bas = np.minimum(ouverture, cloture) * (1 - np.abs(_hasard.normal(0, vol / 2, n)))
    tableau = np.zeros(n, dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                                 ("close", "f8"), ("tick_volume", "i8")])
    tableau["time"] = np.arange(n) * 86400 + 946684800
    tableau["open"], tableau["high"], tableau["low"], tableau["close"] = ouverture, haut, bas, cloture
    return tableau


# nom : (prix de départ, volatilité, décimales, taille du tick, valeur du tick, point)
SYMBOLES_FAUX = {"EURUSDm": (1.1, 0.006, 5, 0.00001, 1.0, 0.00001),
                 "XAUUSDm": (1800, 0.01, 2, 0.001, 0.1, 0.001)}
DONNEES = {nom: _serie(4000, v[0], v[1]) for nom, v in SYMBOLES_FAUX.items()}
faux.CAPITAL = 10000.0

faux.ACCOUNT_TRADE_MODE_DEMO = 0
faux.ACCOUNT_TRADE_MODE_REAL = 2
faux.TRADE_RETCODE_DONE_PARTIAL = 10010
faux.terminal_info = lambda: None
faux.order_calc_profit = lambda *args: -1.0
faux.order_calc_margin = lambda *args: 1.0
faux.order_check = lambda demande: types.SimpleNamespace(retcode=0)
faux.COMPTE = {}


def _initialiser(**params):
    faux.COMPTE.update(params)
    return True


faux.initialize = _initialiser
faux.shutdown = lambda: None
faux.last_error = lambda: (0, "ok")
faux.account_info = lambda: types.SimpleNamespace(login=1, equity=faux.CAPITAL, currency="USC",
                                                  leverage=100, margin_free=faux.CAPITAL,
                                                  server=faux.COMPTE.get("server", ""),
                                                  trade_mode=2 if "Real" in faux.COMPTE.get("server", "") else 0)


def _info(nom):
    if nom not in SYMBOLES_FAUX:
        return None
    _, _, decimales, taille, valeur, point = SYMBOLES_FAUX[nom]
    return types.SimpleNamespace(name=nom, digits=decimales, trade_tick_size=taille,
                                 trade_tick_value=valeur, volume_min=0.01, volume_max=200,
                                 volume_step=0.01, filling_mode=2, spread=12, point=point)


faux.symbol_info = _info
faux.symbols_get = lambda group=None: [types.SimpleNamespace(name=n) for n in SYMBOLES_FAUX
                                       if n.startswith(group.rstrip("*"))]
faux.symbol_select = lambda nom, visible: True
faux.copy_rates_from_pos = lambda s, tf, debut, nb: DONNEES[s][max(0, len(DONNEES[s]) - debut - nb):
                                                                len(DONNEES[s]) - debut]
faux.symbol_info_tick = lambda s: types.SimpleNamespace(ask=DONNEES[s]["close"][-1] * 1.00005,
                                                         bid=DONNEES[s]["close"][-1])
faux.positions_get = lambda symbol=None: []


def _envoyer(demande):
    faux.ENVOIS.append(demande)
    return types.SimpleNamespace(retcode=10009, order=1, price=demande["price"], comment="ok")


faux.order_send = _envoyer
sys.modules["MetaTrader5"] = faux

# Réglages de test (avant l'import de config)
os.chdir(tempfile.mkdtemp())
os.environ.update({"MODE": "TEST", "CLAUDE_ACTIF": "non", "EXNESS_ACTIF": "oui", "HFM_ACTIF": "non",
                   "EXNESS_LOGIN": "1", "EXNESS_SERVEUR": "Exness-MT5Trial9",
                   "COMPTE_REEL_CONFIRME": "non"})

import backtest as B  # noqa: E402
import config as C  # noqa: E402
import indicateurs as ind  # noqa: E402
import risque as R  # noqa: E402
import robot  # noqa: E402
import strategie as S  # noqa: E402
import veto_claude as V  # noqa: E402


def bougies(nom):
    df = pd.DataFrame(DONNEES[nom])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("time")


def test_indicateurs():
    e = ind.even_better_sinewave(bougies("EURUSDm")["close"]).dropna()
    assert e.between(-1.0001, 1.0001).all(), "EBSW hors de [-1, 1]"
    r = ind.rsi(bougies("EURUSDm")["close"], 2)
    assert r.between(0, 100).all(), "RSI hors de [0, 100]"
    print("OK indicateurs")


def test_taille_position():
    standard = types.SimpleNamespace(trade_tick_size=0.00001, trade_tick_value=1.0,
                                     volume_min=0.01, volume_max=200, volume_step=0.01)
    cent = types.SimpleNamespace(trade_tick_size=0.00001, trade_tick_value=0.01,
                                 volume_min=0.01, volume_max=200, volume_step=0.01)
    assert R.taille_position(100, 0.0100, standard)[0] == 0.0, "100 $ standard devrait refuser"
    assert R.taille_position(100, 0.0010, standard)[0] == 0.01
    assert R.taille_position(10000, 0.0100, cent)[0] == 10.0
    print("OK taille de position (standard refusé à 100 $, cent accepté)")


def test_veto():
    assert V.lire_decision('{"decision": "autoriser", "raison": "rien"}')[0] is True
    assert V.lire_decision('texte {"decision": "bloquer", "raison": "BCE"}')[0] is False
    assert V.lire_decision("pas de json")[0] is False
    print("OK lecture du veto (bloque en cas de doute)")


def test_backtest():
    historiques = {nom: (bougies(nom)[["open", "high", "low", "close", "tick_volume"]],
                         12 * SYMBOLES_FAUX[nom][5]) for nom in SYMBOLES_FAUX}
    B.lancer(historiques)
    print("OK backtest (chiffres sans valeur : prix inventés)")


def test_securite_ordres():
    S_original = S.signal_entree
    S.signal_entree = lambda ligne: {"sens": "achat", "module": "TUR", "stop": 0,
                                     "raison": "signal forcé pour le test"}
    try:
        C.MODE = "TEST"
        faux.ENVOIS.clear()
        robot.traiter_courtier(C.COURTIERS[0])
        assert not faux.ENVOIS, "le mode TEST ne doit envoyer aucun ordre"

        C.MODE = "ORDRES"
        C.COURTIERS[0]["serveur"] = "Exness-MT5Real9"
        faux.ENVOIS.clear()
        robot.traiter_courtier(C.COURTIERS[0])
        assert not faux.ENVOIS, "compte réel sans confirmation : aucun ordre"

        C.COURTIERS[0]["serveur"] = "Exness-MT5Trial9"
        faux.ENVOIS.clear()
        robot.traiter_courtier(C.COURTIERS[0])
        assert faux.ENVOIS, "compte démo en mode ORDRES : les ordres doivent partir"
    finally:
        S.signal_entree = S_original
        C.MODE = "TEST"
    print("OK sécurité des ordres (TEST, compte réel bloqué, démo autorisée)")


if __name__ == "__main__":
    test_indicateurs()
    test_taille_position()
    test_veto()
    test_backtest()
    test_securite_ordres()
    print("\nTous les tests sont passés.")
