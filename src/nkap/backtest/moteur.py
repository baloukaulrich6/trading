"""Simulation événementielle D1 en devise USD, sans accès au courtier."""
from collections.abc import Callable
from dataclasses import dataclass
from math import floor, isfinite

import pandas as pd

from nkap.configuration import Limites, Parametres
from nkap.domaine.modeles import Signal, Trade
from nkap.strategies.contrarien import Contrarien
from nkap.strategies.regime import preparer
from nkap.strategies.smc import SMC
from nkap.strategies.turtles import Turtles


@dataclass(frozen=True)
class Couts:
    spread: float
    glissement: float
    commission: float
    swap: float
    valeur_unite_lot: float
    lot_min: float
    pas: float
    claude_par_signal: float = 0.0

    def __post_init__(self) -> None:
        valeurs = (self.spread, self.glissement, self.commission, self.swap, self.valeur_unite_lot,
                   self.lot_min, self.pas, self.claude_par_signal)
        if not all(isfinite(x) and x >= 0 for x in valeurs) or min(valeurs[4:7]) <= 0:
            raise ValueError("Coûts ou caractéristiques du lot invalides.")


@dataclass
class Position:
    signal: Signal
    date: pd.Timestamp
    entree: float
    stop: float
    lots: float
    risque: float
    nuits: int = 0
    sortie_prevue: bool = False


@dataclass(frozen=True)
class Simulation:
    trades: tuple[Trade, ...]
    capital_depart: float
    courbe: tuple[float, ...]
    claude_usd: float
    duree_jours: float


def simuler(marche: str, donnees: pd.DataFrame, p: Parametres, limites: Limites,
            couts: Couts, depart: pd.Timestamp, fin: pd.Timestamp, capital_initial: float, *,
            filtre_signal: Callable[[Signal, pd.Series], bool] | None = None,
            smc: SMC | None = None) -> Simulation:
    if not isfinite(capital_initial) or capital_initial <= 0:
        raise ValueError("Le capital initial doit être positif.")
    donnees = donnees.loc[donnees.index < fin]
    donnees = smc.preparer(donnees, p) if smc is not None else preparer(donnees, p)
    periode = donnees.loc[donnees.index >= depart]
    if periode.empty:
        raise ValueError("Aucune bougie dans la fenêtre de simulation.")
    capital = capital_initial
    sommet = capital
    depuis_perte = 0
    courbe = [capital]
    trades: list[Trade] = []
    claude = 0.0
    position: Position | None = None
    signal: Signal | None = None
    strategies = {"TUR": Turtles(), "CTR": Contrarien()}
    if smc is not None:
        strategies["SMC"] = smc
    execution = (couts.spread + 2 * couts.glissement) * couts.valeur_unite_lot

    def resultat(pos: Position, prix: float) -> float:
        mouvement = prix - pos.entree if pos.signal.sens == "achat" else pos.entree - prix
        frais = execution + couts.commission + couts.swap * pos.nuits
        return (mouvement * couts.valeur_unite_lot - frais) * pos.lots

    def fermer(pos: Position, prix: float, date: pd.Timestamp, motif: str) -> None:
        nonlocal capital, depuis_perte
        net = resultat(pos, prix)
        capital += net
        depuis_perte = depuis_perte + 1 if net < 0 else 0
        trades.append(Trade(pos.signal, pos.date.to_pydatetime(), date.to_pydatetime(),
                            net / pos.risque, net, motif))

    for date, bougie in periode.iterrows():
        ouverture = float(bougie["open"])
        cloture = float(bougie["close"])
        if position is not None:
            position.nuits += max(1, (date.date() - position.date.date()).days - position.nuits)
            if position.sortie_prevue:
                fermer(position, ouverture, date, "règle de sortie")
                position = None
        if position is None and signal is not None:
            distance = signal.distance_stop
            signe = 1 if signal.sens == "achat" else -1
            stop = signal.stop_structurel if signal.stop_structurel is not None else ouverture - signe * distance
            distance = signe * (ouverture - stop)
            risque_lot = max(0, distance) * couts.valeur_unite_lot + execution + couts.commission
            taux = limites.risque_base / (2 if depuis_perte >= limites.reduire_apres else 1)
            lots = (floor(max(0, capital * taux) / risque_lot / couts.pas) * couts.pas
                    if distance > 0 and risque_lot > 0 else 0.0)
            if lots >= couts.lot_min and stop > 0:
                position = Position(signal, date, ouverture, stop, lots, lots * risque_lot)
        signal = None
        if position is not None:
            achat = position.signal.sens == "achat"
            stop_touche = bougie["low"] <= position.stop if achat else bougie["high"] >= position.stop
            if stop_touche:
                prix = min(position.stop, ouverture) if achat else max(position.stop, ouverture)
                fermer(position, prix, date, "stop")
                position = None
            elif date == periode.index[-1]:
                fermer(position, cloture, date, "fin de fenêtre")
                position = None
            else:
                position.sortie_prevue = strategies[position.signal.module].sortir(
                    bougie, position.signal.sens
                )

        valeur = capital + (resultat(position, cloture) if position is not None else 0)
        sommet = max(sommet, valeur)
        if (position is None and date != periode.index[-1] and (smc is not None or pd.notna(bougie["tendance"]))
                and bougie["atr"] > 0 and capital >= sommet * (1 - limites.drawdown_max)
                and depuis_perte < limites.pause_apres):
            module = "SMC" if smc is not None else "TUR" if bougie["tendance"] else "CTR"
            signal = strategies[module].entree(marche, bougie, p)
            if signal is not None and filtre_signal is not None and not filtre_signal(signal, bougie):
                signal = None
            if signal is not None:
                capital -= couts.claude_par_signal
                claude += couts.claude_par_signal
                valeur = capital
        courbe.append(valeur)

    return Simulation(tuple(trades), capital_initial, tuple(courbe), claude,
                      max(1.0, (fin - depart).total_seconds() / 86400))
