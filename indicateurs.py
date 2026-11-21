"""Indicateurs : ATR, canaux de Donchian, moyennes, RSI et Even Better Sinewave d'Ehlers."""
import math

import numpy as np
import pandas as pd


def sma(serie: pd.Series, n: int) -> pd.Series:
    return serie.rolling(n).mean()


def atr(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """N des Turtles : moyenne lissée (Wilder) du True Range."""
    cloture_prec = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - cloture_prec).abs(),
            (df["low"] - cloture_prec).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def plus_haut(serie: pd.Series, n: int) -> pd.Series:
    """Plus haut des n bougies PRÉCÉDENTES (la bougie du jour n'est pas comptée)."""
    return serie.rolling(n).max().shift(1)


def plus_bas(serie: pd.Series, n: int) -> pd.Series:
    """Plus bas des n bougies PRÉCÉDENTES."""
    return serie.rolling(n).min().shift(1)


def rsi(cloture: pd.Series, n: int = 2) -> pd.Series:
    variation = cloture.diff()
    hausse = variation.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    baisse = (-variation.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = hausse / baisse.replace(0, np.nan)
    resultat = 100 - 100 / (1 + rs)
    return resultat.fillna(100.0)


def even_better_sinewave(cloture: pd.Series, duree: int = 40, lissage: int = 10) -> pd.Series:
    """Even Better Sinewave (John Ehlers, Cycle Analytics for Traders).

    Valeur entre -1 et +1. Proche de +1 ou -1 longtemps : tendance.
    Oscille autour de 0 : marché en cycle.
    """
    c = cloture.to_numpy(dtype=float)
    n = len(c)

    # Filtre passe-haut : retire la tendance de fond plus longue que `duree`
    alpha1 = (1 - math.sin(2 * math.pi / duree)) / math.cos(2 * math.pi / duree)

    # Super Smoother : retire le bruit plus court que `lissage`
    a1 = math.exp(-1.414 * math.pi / lissage)
    b1 = 2 * a1 * math.cos(1.414 * math.pi / lissage)
    c2 = b1
    c3 = -a1 * a1
    c1 = 1 - c2 - c3

    hp = np.zeros(n)
    filt = np.zeros(n)
    vague = np.full(n, np.nan)

    for i in range(1, n):
        hp[i] = 0.5 * (1 + alpha1) * (c[i] - c[i - 1]) + alpha1 * hp[i - 1]
        f2 = filt[i - 2] if i >= 2 else 0.0
        filt[i] = c1 * (hp[i] + hp[i - 1]) / 2 + c2 * filt[i - 1] + c3 * f2
        if i >= 2:
            moyenne = (filt[i] + filt[i - 1] + filt[i - 2]) / 3
            puissance = (filt[i] ** 2 + filt[i - 1] ** 2 + filt[i - 2] ** 2) / 3
            vague[i] = moyenne / math.sqrt(puissance) if puissance > 0 else 0.0

    return pd.Series(vague, index=cloture.index)
