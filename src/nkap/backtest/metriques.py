"""Mesures nettes et tirages reproductibles de pertes maximales."""
from dataclasses import dataclass
from math import inf

import numpy as np

from nkap.backtest.moteur import Simulation


@dataclass(frozen=True)
class Mesures:
    profit_usd: float
    annualise: float
    drawdown: float
    calmar: float | None
    facteur_profit: float
    trades: int
    cout_claude_usd: float


def perte_maximale(courbe: tuple[float, ...]) -> float:
    sommet = courbe[0]
    perte = 0.0
    for capital in courbe:
        sommet = max(sommet, capital)
        perte = max(perte, 1 - capital / sommet)
    return perte


def mesurer(s: Simulation) -> Mesures:
    resultat = s.courbe[-1] - s.capital_depart
    annualise = max(0.0, s.courbe[-1] / s.capital_depart) ** (365.25 / s.duree_jours) - 1
    dd = perte_maximale(s.courbe)
    gains = sum(max(t.resultat_usd, 0.0) for t in s.trades)
    pertes = s.claude_usd + sum(max(-t.resultat_usd, 0.0) for t in s.trades)
    facteur = gains / pertes if pertes else inf if gains else 0.0
    return Mesures(resultat, annualise, dd, annualise / dd if dd else None, facteur,
                   len(s.trades), s.claude_usd)


def monte_carlo(s: Simulation, *, tirages: int = 1000, graine: int = 42) -> float | None:
    """Rééchantillonne les P&L clôturés. Ne reproduit pas le risque intrajournalier."""
    gains = [t.resultat_usd - s.claude_usd / len(s.trades) for t in s.trades]
    if not gains:
        return None
    choix = np.random.default_rng(graine).choice(gains, size=(tirages, len(gains)), replace=True)
    courbes = np.column_stack((np.full(tirages, s.capital_depart),
                              s.capital_depart + np.cumsum(choix, axis=1)))
    pertes = np.max(1 - courbes / np.maximum.accumulate(courbes, axis=1), axis=1)
    return float(np.quantile(pertes, 0.95))
