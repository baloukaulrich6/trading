"""Connexion à un terminal MetaTrader 5 (Exness ou HFM) : données, positions et ordres."""
import logging
import os
from math import isfinite

import MetaTrader5 as mt5
import pandas as pd

import config as C

log = logging.getLogger("robot")


class Courtier:
    def __init__(self, conf: dict):
        self.nom = conf["nom"]
        self.login = conf["login"]
        self.mot_de_passe = conf["mot_de_passe"]
        self.serveur = conf["serveur"]
        self.chemin = conf["chemin"]

    # ---------- connexion ----------
    def connecter(self) -> None:
        params = {"login": self.login, "password": self.mot_de_passe,
                  "server": self.serveur, "timeout": C.MT5_TIMEOUT_MS}
        if self.chemin:
            params["path"] = self.chemin
        if not mt5.initialize(**params):
            raise ConnectionError(f"{self.nom} : connexion impossible {mt5.last_error()}")
        log.info("%s connecté (serveur %s)", self.nom, self.serveur)

    def deconnecter(self) -> None:
        mt5.shutdown()

    def est_compte_reel(self) -> bool:
        compte = self.infos_compte()
        return (compte is None or getattr(compte, "trade_mode", None)
                != mt5.ACCOUNT_TRADE_MODE_DEMO)

    def verifier_envoi(self) -> None:
        compte = self.infos_compte()
        if (compte is None or not self.login or compte.login != self.login
                or not self.serveur or compte.server.casefold() != self.serveur.casefold()):
            raise RuntimeError("Compte MT5 actif différent du compte configuré.")
        if C.MODE != "ORDRES":
            raise RuntimeError("MODE=ORDRES est requis pour envoyer un ordre.")
        if (compte.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO
                and os.getenv("COMPTE_REEL_CONFIRME", "").strip().lower() != "oui"):
            raise RuntimeError("La confirmation du compte réel est requise.")

    def positions_symbole(self, symbole: str) -> list:
        positions = mt5.positions_get(symbol=symbole)
        if positions is None:
            raise RuntimeError(f"Positions MT5 indisponibles pour {symbole} : {mt5.last_error()}")
        return list(positions)

    # ---------- informations ----------
    def infos_compte(self):
        return mt5.account_info()

    def info_symbole(self, symbole: str):
        return mt5.symbol_info(symbole)

    def trouver_symbole(self, base: str):
        """Trouve le vrai nom du symbole chez le courtier (EURUSD, EURUSDm, EURUSDc...)."""
        compte = self.infos_compte() if self.nom == "HFM" else None
        if compte is not None and compte.currency.upper() == "USC":
            nom = base + "c"
            if mt5.symbol_info(nom) is None:
                return None
        elif mt5.symbol_info(base) is not None:
            nom = base
        else:
            candidats = [s.name for s in (mt5.symbols_get(group=f"{base}*") or [])
                         if s.name.startswith(base)]
            if not candidats:
                return None
            nom = min(candidats, key=len)
        return nom if mt5.symbol_select(nom, True) else None

    def bougies(self, symbole: str, nombre: int = 400) -> pd.DataFrame:
        """Bougies journalières CLÔTURÉES (la bougie en cours est exclue)."""
        donnees = mt5.copy_rates_from_pos(symbole, mt5.TIMEFRAME_D1, 1, nombre)
        if donnees is None or len(donnees) == 0:
            raise ValueError(f"{self.nom} : aucune donnée pour {symbole} {mt5.last_error()}")
        df = pd.DataFrame(donnees)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df.set_index("time")[["open", "high", "low", "close", "tick_volume"]]

    def prix_actuel(self, symbole: str, sens: str) -> float:
        tick = mt5.symbol_info_tick(symbole)
        if tick is None:
            raise ValueError(f"Cotation MT5 indisponible pour {symbole}.")
        return tick.ask if sens == "achat" else tick.bid

    def cout_ordre(self, symbole: str, sens: str, volume: float, prix: float, stop: float):
        """Retourne le risque au stop et la marge, dans la devise du compte."""
        if not all(isfinite(v) and v > 0 for v in (volume, prix, stop)):
            raise ValueError("Prix, volume ou stop invalide.")
        type_ordre = mt5.ORDER_TYPE_BUY if sens == "achat" else mt5.ORDER_TYPE_SELL
        profit = mt5.order_calc_profit(type_ordre, symbole, volume, prix, stop)
        marge = mt5.order_calc_margin(type_ordre, symbole, volume, prix)
        if profit is None or marge is None or not isfinite(profit) or not isfinite(marge):
            raise ValueError(f"Calcul du risque ou de la marge indisponible pour {symbole}.")
        if profit >= 0 or marge < 0:
            raise ValueError(f"Stop ou marge incohérent pour {symbole}.")
        return -profit, marge

    def positions(self, symbole: str = None) -> list:
        brutes = self.positions_symbole(symbole) if symbole else mt5.positions_get()
        if brutes is None:
            raise RuntimeError(f"Positions MT5 indisponibles : {mt5.last_error()}")
        return [p for p in brutes if p.magic == C.MAGIC]

    # ---------- ordres ----------
    @staticmethod
    def _remplissage(info) -> int:
        """Mode de remplissage accepté par le symbole (évite l'erreur 'Unsupported filling mode')."""
        if info.filling_mode & 1:      # FOK autorisé
            return mt5.ORDER_FILLING_FOK
        if info.filling_mode & 2:      # IOC autorisé
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def ouvrir(self, symbole: str, sens: str, volume: float, stop: float, module: str):
        self.verifier_envoi()
        if self.positions_symbole(symbole):
            return False, "une position existe déjà sur ce symbole"
        info = mt5.symbol_info(symbole)
        prix = self.prix_actuel(symbole, sens)
        stop = round(float(stop), info.digits)
        compte = self.infos_compte()
        try:
            risque, marge = self.cout_ordre(symbole, sens, volume, prix, stop)
        except ValueError as erreur:
            return False, str(erreur)
        if risque > compte.equity * C.RISQUE_PAR_TRADE:
            return False, f"perte au stop recalculée trop élevée ({risque:.2f} {compte.currency})"
        if marge > compte.margin_free:
            return False, f"marge insuffisante ({marge:.2f} {compte.currency} requise)"
        demande = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbole,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if sens == "achat" else mt5.ORDER_TYPE_SELL,
            "price": prix,
            "sl": stop,
            "deviation": 20,
            "magic": C.MAGIC,
            "comment": module,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._remplissage(info),
        }
        controle = mt5.order_check(demande)
        if controle is None:
            return False, f"contrôle MT5 indisponible ({mt5.last_error()})"
        if controle.retcode != 0:
            return False, f"contrôle MT5 refusé ({controle.retcode} : {controle.comment})"
        self.verifier_envoi()
        resultat = mt5.order_send(demande)
        if resultat is None:
            return False, f"order_send a échoué {mt5.last_error()}"
        if resultat.retcode == mt5.TRADE_RETCODE_DONE_PARTIAL:
            return True, f"ordre {resultat.order} partiellement exécuté"
        if resultat.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"refusé (code {resultat.retcode} : {resultat.comment})"
        return True, f"ordre {resultat.order} exécuté à {resultat.price}"

    def fermer(self, position):
        self.verifier_envoi()
        position = next((p for p in self.positions(position.symbol)
                         if p.ticket == position.ticket), None)
        if position is None:
            return False, "ticket du robot introuvable"
        info = mt5.symbol_info(position.symbol)
        vente = position.type == mt5.POSITION_TYPE_BUY
        demande = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if vente else mt5.ORDER_TYPE_BUY,
            "position": position.ticket,
            "price": self.prix_actuel(position.symbol, "vente" if vente else "achat"),
            "deviation": 20,
            "magic": C.MAGIC,
            "comment": "sortie",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._remplissage(info),
        }
        resultat = mt5.order_send(demande)
        if resultat is None or resultat.retcode != mt5.TRADE_RETCODE_DONE:
            code = resultat.retcode if resultat else mt5.last_error()
            return False, f"fermeture refusée ({code})"
        return True, f"position {position.ticket} fermée à {resultat.price}"
