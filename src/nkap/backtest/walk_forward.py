"""Sélection ancrée sur le passé et validation sur les années suivantes."""
from dataclasses import dataclass

import pandas as pd

from nkap.agents.analyste import analyser
from nkap.agents.eclaireur import Observation
from nkap.agents.filtre import filtrer
from nkap.agents.meteo import Meteo
from nkap.backtest.metriques import Mesures, mesurer, monte_carlo
from nkap.backtest.moteur import Couts, Simulation, simuler
from nkap.configuration import Limites, Parametres
from nkap.domaine.modeles import Signal


@dataclass(frozen=True)
class Fenetre:
    debut: str
    fin_exclue: str
    version: str
    mesures: Mesures


@dataclass(frozen=True)
class Evaluation:
    fenetres: tuple[Fenetre, ...]
    mesures: Mesures
    drawdown_mc_95: float | None
    refus: tuple[str, ...]
    reserve_debut: str
    reserve_fin_exclue: str


def motifs_refus(m: Mesures, fenetres: tuple[Fenetre, ...]) -> tuple[str, ...]:
    motifs = []
    if m.facteur_profit < 1.2:
        motifs.append("Facteur de profit net inférieur à 1,2")
    if m.drawdown > 0.20:
        motifs.append("Perte maximale supérieure à 20 %")
    if m.trades < 100:
        motifs.append("Moins de 100 trades hors échantillon")
    if len(fenetres) < 3 or sum(f.mesures.profit_usd > 0 for f in fenetres[-3:]) < 2:
        motifs.append("Moins de deux fenêtres rentables sur les trois dernières")
    if m.profit_usd <= 0 or m.cout_claude_usd > 0.10 * m.profit_usd:
        motifs.append("Profit net non positif ou coût Claude supérieur à 10 % du profit")
    return tuple(motifs)


def walk_forward(marche: str, donnees: pd.DataFrame, champion: Parametres, limites: Limites,
                 couts: Couts, capital: float, *, comparer_regimes: bool = True,
                 avec_agents: bool = False) -> Evaluation:
    origine = donnees.index[0]
    fin = donnees.index[-1] + pd.Timedelta(seconds=1)
    reserve = fin - pd.DateOffset(years=1)
    debut = origine + pd.DateOffset(years=3)
    if debut + pd.DateOffset(years=3) > reserve:
        raise ValueError("Sept années de bougies sont nécessaires pour trois tests annuels et la réserve.")
    candidats = [champion]
    if comparer_regimes:
        autre = "er" if champion.regime == "ebsw" else "ebsw"
        candidats.append(replace_parametres(champion, autre))
    courbe = [capital]
    trades = []
    cout_total = 0.0
    duree = 0.0
    fenetres = []
    plafond_formation = donnees.loc[donnees.index < reserve]
    while (fin_fenetre := debut + pd.DateOffset(years=1)) <= reserve:
        formations = [
            (p, simuler(marche, plafond_formation, p, limites, couts, origine, debut, capital))
            for p in candidats
        ]
        choisi, formation = max(formations, key=lambda paire: score_formation(paire[1]))

        if courbe[-1] <= 0:
            break
        filtre = filtre_historique(formation, couts) if avec_agents else None
        resultat = simuler(marche, plafond_formation, choisi, limites, couts, debut, fin_fenetre,
                           courbe[-1], filtre_signal=filtre)
        fenetres.append(Fenetre(debut.isoformat(), fin_fenetre.isoformat(), choisi.version, mesurer(resultat)))
        courbe.extend(resultat.courbe[1:])
        trades.extend(resultat.trades)
        cout_total += resultat.claude_usd
        duree += resultat.duree_jours
        debut = fin_fenetre

    ensemble = Simulation(tuple(trades), capital, tuple(courbe), cout_total, duree)
    mesures = mesurer(ensemble)
    toutes = tuple(fenetres)
    return Evaluation(toutes, mesures, monte_carlo(ensemble), motifs_refus(mesures, toutes),
                      reserve.isoformat(), fin.isoformat())


def score_formation(simulation: Simulation) -> float:
    formation = mesurer(simulation)
    return (formation.calmar if formation.calmar is not None and formation.profit_usd > 0
            else float("-inf"))


def filtre_historique(formation: Simulation, couts: Couts):
    par_module = {
        module: tuple(t.resultat_r for t in formation.trades if t.signal.module == module)
        for module in ("TUR", "CTR")
    }

    def accepter(signal: Signal, ligne: pd.Series) -> bool:
        observation = Observation(signal, ligne["atr"], couts.spread, ligne["high"] - ligne["low"],
                                  0.0, True, par_module[signal.module])
        contexte = Meteo(False, "Météo non simulée")
        decision = filtrer(observation, contexte, en_pause=False, pari_risque=False)
        return decision.autorisee and analyser(observation).decision.autorisee

    return accepter


def replace_parametres(p: Parametres, regime: str) -> Parametres:
    return Parametres.model_validate({**p.model_dump(), "regime": regime, "version": f"{p.version}-{regime}"})


def verifier_reserve(marche: str, donnees: pd.DataFrame, champion: Parametres, limites: Limites,
                     couts: Couts, capital: float, evaluation: Evaluation) -> Mesures:
    if evaluation.refus:
        raise ValueError("Le walk-forward a échoué. Conserve la réserve intacte.")
    return mesurer(simuler(marche, donnees, champion, limites, couts, pd.Timestamp(evaluation.reserve_debut),
                          pd.Timestamp(evaluation.reserve_fin_exclue), capital))
