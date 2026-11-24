"""Adaptateur du terminal MT5, utilisable avec le module réel ou un double de test."""
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import blake2s
from math import isfinite
from typing import Any

from nkap.configuration import Limites
from nkap.domaine.modeles import Ordre, Sens
from nkap.execution.ordres import Compte, Reponse
from nkap.risque.limites import EtatRisque, autoriser


def reference(identifiant: str) -> str:
    return "NK-" + blake2s(identifiant.encode(), digest_size=10).hexdigest()


class CourtierMT5:
    def __init__(self, api: Any, symboles: dict[str, str], magic: int, limites: Limites,
                 etat_risque: Callable[[], EtatRisque],
                 expositions: Callable[[Ordre], tuple[tuple[str, Sens], ...]]) -> None:
        self.api = api
        self.symboles = symboles
        self.magic = magic
        self.limites = limites
        self.etat_risque = etat_risque
        self.expositions = expositions
        self.identite = self.compte().identifiant

    def compte(self) -> Compte:
        compte = self.api.account_info()
        if compte is None:
            raise RuntimeError("Compte MT5 indisponible")
        if compte.trade_mode not in (self.api.ACCOUNT_TRADE_MODE_DEMO, self.api.ACCOUNT_TRADE_MODE_REAL):
            raise RuntimeError("Type de compte MT5 non pris en charge")
        return Compte(f"{compte.server.casefold()}:{compte.login}",
                      compte.trade_mode == self.api.ACCOUNT_TRADE_MODE_DEMO)

    def _demande(self, ordre: Ordre) -> dict[str, object] | None:
        mt5 = self.api
        symbole = self.symboles.get(ordre.signal.marche)
        if not symbole or self.compte().identifiant != self.identite:
            return None
        positions = mt5.positions_get(symbol=symbole)
        ordres = mt5.orders_get(symbol=symbole)
        if positions is None or ordres is None or positions or ordres:
            return None
        info = mt5.symbol_info(symbole)
        tick = mt5.symbol_info_tick(symbole)
        compte = mt5.account_info()
        if info is None or tick is None or compte is None:
            return None
        achat = ordre.signal.sens == "achat"
        sens = mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL
        prix = tick.ask if achat else tick.bid
        stop = round(ordre.stop, info.digits)
        if not all(isfinite(v) and v > 0 for v in (prix, stop, ordre.volume)):
            return None
        if (prix <= stop if achat else prix >= stop):
            return None
        resultat = mt5.order_calc_profit(sens, symbole, ordre.volume, prix, stop)
        marge = mt5.order_calc_margin(sens, symbole, ordre.volume, prix)
        if (resultat is None or not isfinite(resultat) or resultat >= 0
                or marge is None or not isfinite(marge) or not 0 <= marge <= compte.margin_free):
            return None
        risque = autoriser(self.etat_risque(), -resultat, self.expositions(ordre), self.limites)
        if not risque.autorisee:
            return None
        remplissage = (mt5.ORDER_FILLING_FOK if info.filling_mode & 1 else
                       mt5.ORDER_FILLING_IOC if info.filling_mode & 2 else mt5.ORDER_FILLING_RETURN)
        return {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbole, "volume": ordre.volume,
                "type": sens, "price": prix, "sl": stop, "magic": self.magic,
                "comment": reference(ordre.identifiant), "deviation": 20,
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": remplissage}

    def disponible(self, ordre: Ordre) -> bool:
        return self._demande(ordre) is not None

    def envoyer(self, ordre: Ordre) -> Reponse:
        demande = self._demande(ordre)
        if demande is None:
            return Reponse("refuse", "Compte, risque, marge ou position incompatible")
        controle = self.api.order_check(demande)
        if controle is None or controle.retcode != 0:
            return Reponse("refuse", "Contrôle préalable MT5 refusé")
        if self.compte().identifiant != self.identite:
            return Reponse("refuse", "Le compte MT5 a changé")
        resultat = self.api.order_send(demande)
        if resultat is None:
            return Reponse("incertain", "Aucune réponse MT5")
        if resultat.retcode in (self.api.TRADE_RETCODE_DONE, self.api.TRADE_RETCODE_DONE_PARTIAL):
            ticket = resultat.deal or resultat.order
            return Reponse("execute" if ticket else "incertain", "Exécution MT5", str(ticket) if ticket else None)
        return Reponse("incertain", f"Résultat MT5 à rapprocher (code {resultat.retcode})")

    def rechercher(self, identifiant: str) -> Reponse:
        if self.compte().identifiant != self.identite:
            return Reponse("incertain", "Le compte MT5 a changé")
        for element in self.api.positions_get() or ():
            if element.magic == self.magic and element.comment == reference(identifiant):
                return Reponse("execute", "Position confirmée sur MT5", str(element.ticket))
        maintenant = datetime.now(UTC)
        for deal in self.api.history_deals_get(maintenant - timedelta(days=7), maintenant) or ():
            if deal.magic == self.magic and deal.comment == reference(identifiant):
                return Reponse("execute", "Transaction confirmée dans l’historique MT5", str(deal.ticket))
        return Reponse("incertain", "Aucune position correspondante visible")

    def resserrer_stop(self, ticket: int, stop: float) -> bool:
        mt5 = self.api
        if self.compte().identifiant != self.identite:
            return False
        positions = mt5.positions_get(ticket=ticket)
        if not positions or positions[0].magic != self.magic:
            return False
        p = positions[0]
        info = mt5.symbol_info(p.symbol)
        tick = mt5.symbol_info_tick(p.symbol)
        if info is None or tick is None or not isfinite(stop):
            return False
        stop = round(stop, info.digits)
        achat = p.type == mt5.POSITION_TYPE_BUY
        if p.sl <= 0 or not (p.sl < stop < tick.bid if achat else tick.ask < stop < p.sl):
            return False
        demande = {"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "symbol": p.symbol,
                   "sl": stop, "tp": p.tp}
        if self.compte().identifiant != self.identite:
            return False
        reponse = mt5.order_send(demande)
        return bool(reponse is not None and reponse.retcode == mt5.TRADE_RETCODE_DONE)
