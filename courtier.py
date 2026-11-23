"""Connexion à un terminal MetaTrader 5 (Exness ou HFM) : données, positions et ordres."""
import logging

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
        nom = self.serveur.lower()
        return "real" in nom or "live" in nom

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
        brutes = mt5.positions_get(symbol=symbole) if symbole else mt5.positions_get()
        return [p for p in (brutes or []) if p.magic == C.MAGIC]

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
        if resultat.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"refusé (code {resultat.retcode} : {resultat.comment})"
        return True, f"ordre {resultat.order} exécuté à {resultat.price}"

    def fermer(self, position):
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
