"""Connexion à un terminal MetaTrader 5 (Exness ou HFM) : données, positions et ordres."""
import logging
import os

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
        if mt5.symbol_info(base) is not None:
            nom = base
        else:
            candidats = [s.name for s in (mt5.symbols_get(group=f"{base}*") or [])
                         if s.name.startswith(base)]
            if not candidats:
                return None
            nom = min(candidats, key=len)
        mt5.symbol_select(nom, True)
        return nom

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
        return tick.ask if sens == "achat" else tick.bid

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
        demande = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbole,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if sens == "achat" else mt5.ORDER_TYPE_SELL,
            "price": self.prix_actuel(symbole, sens),
            "sl": round(float(stop), info.digits),
            "deviation": 20,
            "magic": C.MAGIC,
            "comment": module,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._remplissage(info),
        }
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
