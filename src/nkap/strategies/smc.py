"""Structure de marché SMC sur bougies clôturées, sans anticipation."""
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from nkap.configuration import Parametres
from nkap.domaine.modeles import Sens, Signal
from nkap.indicateurs.calculs import atr

Cassure = Literal["BOS", "CHoCH"]


@dataclass(frozen=True)
class Zone:
    sens: Sens
    bas: float
    haut: float
    indice: int


@dataclass(frozen=True)
class ReglagesSMC:
    pivot: int = 2
    age_zone: int = 12
    score_min: int = 65

    def __post_init__(self) -> None:
        if self.pivot < 1 or self.age_zone < 1 or not 0 <= self.score_min <= 100:
            raise ValueError("Les réglages SMC sont hors limites.")


def _pivot(valeurs: list[float], debut: int, largeur: int, *, haut: bool) -> float | None:
    centre = debut + largeur
    milieu = valeurs[centre]
    voisins = valeurs[debut:centre] + valeurs[centre + 1:centre + largeur + 1]
    extremum = max(voisins) if haut else min(voisins)
    return milieu if (milieu > extremum if haut else milieu < extremum) else None


class SMC:
    def __init__(self, reglages: ReglagesSMC = ReglagesSMC()) -> None:
        self.reglages = reglages

    def preparer(self, donnees: pd.DataFrame, p: Parametres) -> pd.DataFrame:
        r = self.reglages
        tailles = atr(donnees, p.periode_atr).to_list()
        hauts, bas = donnees["high"].to_list(), donnees["low"].to_list()
        pivot_haut = pivot_bas = None
        regime: Sens | None = None
        zones: list[Zone] = []
        resultats = []
        for i, bougie in enumerate(donnees.itertuples()):
            if i >= 2 * r.pivot:
                debut = i - 2 * r.pivot
                ph = _pivot(hauts, debut, r.pivot, haut=True)
                pb = _pivot(bas, debut, r.pivot, haut=False)
                if ph is not None:
                    pivot_haut = ph
                if pb is not None:
                    pivot_bas = pb

            zones = [z for z in zones if i - z.indice <= r.age_zone and (
                bougie.low > z.bas if z.sens == "achat" else bougie.high < z.haut
            )]
            taille = tailles[i]
            if i >= 2 and taille > 0:
                if bas[i] - hauts[i - 2] >= .10 * taille:
                    zones.append(Zone("achat", hauts[i - 2], bas[i], i))
                elif bas[i - 2] - hauts[i] >= .10 * taille:
                    zones.append(Zone("vente", hauts[i], bas[i - 2], i))

            sens: Sens | None = None
            niveau_protecteur = None
            if pivot_haut is not None and bougie.close > pivot_haut:
                sens, niveau_protecteur, pivot_haut = "achat", pivot_bas, None
            elif pivot_bas is not None and bougie.close < pivot_bas:
                sens, niveau_protecteur, pivot_bas = "vente", pivot_haut, None

            evenement: Cassure | None = None
            score = 0
            distance = None
            fvg = None
            if sens is not None:
                evenement = "CHoCH" if regime is not None and regime != sens else "BOS"
                score = 35
                fvg = next((z for z in reversed(zones) if z.sens == sens), None)
                if fvg is not None:
                    score += 30
                signe = 1 if sens == "achat" else -1
                if signe * (bougie.close - bougie.open) >= .6 * taille:
                    score += 20
                if regime == sens:
                    score += 15
                if niveau_protecteur is not None and taille > 0:
                    ecart = signe * (bougie.close - niveau_protecteur)
                    if ecart > 0:
                        distance = ecart + .10 * taille
                regime = sens
            resultats.append((evenement, sens, score, distance, fvg.bas if fvg else None,
                              fvg.haut if fvg else None))
        colonnes = ("smc_evenement", "smc_sens", "smc_score", "smc_stop", "fvg_bas", "fvg_haut")
        structure = pd.DataFrame(resultats, columns=colonnes, index=donnees.index)
        structure = structure.astype({"smc_evenement": "string", "smc_sens": "string",
                                     "smc_stop": float, "fvg_bas": float, "fvg_haut": float})
        return donnees.join(structure).assign(atr=tailles)

    def entree(self, marche: str, ligne: pd.Series, p: Parametres) -> Signal | None:
        if (pd.notna(ligne["smc_sens"]) and ligne["smc_score"] >= self.reglages.score_min
                and pd.notna(ligne["smc_stop"])):
            return Signal(marche, ligne.name.to_pydatetime(), ligne["smc_sens"], "SMC", ligne["smc_stop"])
        return None

    def sortir(self, ligne: pd.Series, sens: Sens) -> bool:
        """Déclenche une sortie après une cassure confirmée dans le sens opposé."""
        oppose = "vente" if sens == "achat" else "achat"
        return bool(pd.notna(ligne["smc_sens"]) and ligne["smc_sens"] == oppose)
