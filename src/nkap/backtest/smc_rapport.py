"""Évaluation SMC sur cinq ans et export du journal de simulation."""
import json
from dataclasses import asdict
from html import escape
from pathlib import Path

import pandas as pd

from nkap.backtest.metriques import mesurer, monte_carlo
from nkap.backtest.moteur import Couts, Simulation, simuler
from nkap.configuration import Limites, Parametres
from nkap.strategies.smc import SMC


def evaluer_cinq_ans(marche: str, data: pd.DataFrame, p: Parametres, limites: Limites,
                     couts: Couts, capital: float, fin: pd.Timestamp,
                     *, ouvrir_reserve: bool = False) -> tuple[dict, Simulation]:
    debut = fin - pd.DateOffset(years=5)
    hors_echantillon = fin - pd.DateOffset(years=2)
    reserve = fin - pd.DateOffset(years=1)
    serie = data.loc[(data.index >= debut) & (data.index < fin)]
    if (serie.empty or serie.index[0] - debut > pd.Timedelta(days=5)
            or fin - serie.index[-1] > pd.Timedelta(days=5)):
        raise ValueError("Il faut cinq années complètes de bougies clôturées, jusqu'à la date choisie.")
    strategie = SMC()
    reglage = simuler(marche, serie, p, limites, couts, debut, hors_echantillon, capital, smc=strategie)
    test = simuler(marche, serie, p, limites, couts, hors_echantillon, reserve, capital, smc=strategie)
    mesures = mesurer(test)
    rapport = {
        "marche": marche, "strategie": "SMC", "admission_reel": False,
        "formation": {"debut": debut.isoformat(), "fin_exclue": hors_echantillon.isoformat(),
                      "mesures": asdict(mesurer(reglage)), "entrees": asdict(reglage.entrees)},
        "hors_echantillon": {"debut": hors_echantillon.isoformat(), "fin_exclue": reserve.isoformat(),
                             "mesures": asdict(mesures), "entrees": asdict(test.entrees)},
        "reserve_debut": reserve.isoformat(),
        "reserve_fin_exclue": fin.isoformat(),
        "win_rate": (sum(t.resultat_usd > 0 for t in test.trades) / len(test.trades)
                     if test.trades else None),
        "drawdown_mc_95": monte_carlo(test),
        "nombre_trades_suffisant": mesures.trades >= 100,
    }
    if ouvrir_reserve:
        dernier = simuler(marche, serie, p, limites, couts, reserve, fin, capital, smc=strategie)
        rapport["reserve"] = asdict(mesurer(dernier))
    return rapport, test


def ecrire_html(destination: Path, rapport: dict, s: Simulation) -> None:
    mesures = mesurer(s)
    sym = escape(rapport["marche"])
    wr = rapport["win_rate"]
    taux = f"{wr:.1%}" if wr is not None else "—"
    pf = f"{mesures.facteur_profit:.2f}" if mesures.facteur_profit < float("inf") else "∞"
    lignes = "".join(
        "<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in
                         (t.date_entree.date(), t.date_sortie.date(), t.signal.sens,
                          f"{t.resultat_r:+.2f}", f"{t.resultat_usd:+.2f}", t.motif)) + "</tr>"
        for t in s.trades
    )
    courbe = json.dumps(s.courbe, allow_nan=False)
    e = s.entrees
    minimum = (f"<p>Plus petit capital estimé parmi les entrées refusées pour taille : "
               f"<strong>{e.capital_min_usd:.2f} USD</strong>.</p>" if e.capital_min_usd is not None else "")
    destination.write_text(f"""<!doctype html>
<html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nkap · Backtest SMC</title><style>
body{{max-width:1100px;margin:30px auto;padding:0 18px;background:#11171d;color:#ecf2f6;font:15px system-ui}}
section{{border:1px solid #2c3c48;border-radius:9px;padding:15px;margin:14px 0;background:#17222b;overflow:auto}}
h1,h2,p{{margin:0 0 12px}} .stats{{display:flex;gap:24px;flex-wrap:wrap}} strong{{color:#80e9b6}}
canvas{{width:100%;height:240px}} table{{width:100%;border-collapse:collapse;white-space:nowrap}}
th,td{{text-align:left;padding:9px;border-bottom:1px solid #2c3c48}}
</style><main><h1>Rapport SMC · {sym}</h1><p>Simulation hors échantillon · Résultats en USD</p>
<section class="stats"><span>Résultat net <strong>{mesures.profit_usd:+.2f}</strong></span>
<span>Win rate <strong>{taux}</strong></span><span>Profit factor <strong>{pf}</strong></span>
<span>Drawdown <strong>{mesures.drawdown:.1%}</strong></span><span>Trades <strong>{mesures.trades}</strong></span></section>
<section><h2>Analyse des entrées</h2><p>{e.signaux} signaux · {e.capital_insuffisant} refus pour lot minimal ·
{e.stop_invalide} stops invalidés à l’ouverture · {e.position_existante} positions existantes ·
{e.coupe_circuit} coupe-circuits · {e.filtres} refus par les filtres.</p>{minimum}</section>
<section><h2>Courbe d’équité</h2><canvas id="equite" role="img" aria-label="Courbe de capital simulé"></canvas></section>
<section><h2>Journal des trades simulés</h2><table><thead><tr><th>Entrée</th><th>Sortie</th><th>Sens</th>
<th>Net (R)</th><th>Net (USD)</th><th>Motif</th></tr></thead>
<tbody>{lignes or '<tr><td colspan="6">Aucun trade simulé.</td></tr>'}</tbody></table></section>
<script>
const donnees={courbe}, canvas=document.querySelector("canvas");
function dessiner(){{
  const w=canvas.clientWidth,h=canvas.clientHeight;
  canvas.width=w*devicePixelRatio;canvas.height=h*devicePixelRatio;
  const c=canvas.getContext("2d");c.scale(devicePixelRatio,devicePixelRatio);
  const min=Math.min(...donnees),max=Math.max(...donnees),marge=(max-min)*.05||1;
  const bas=min-marge,haut=max+marge;
  for(let i=0;i<5;i++){{
    const y=12+i*(h-24)/4;c.strokeStyle="#2c3c48";c.beginPath();c.moveTo(45,y);c.lineTo(w,y);c.stroke();
    c.fillStyle="#b5c1cc";c.fillText((haut-i*(haut-bas)/4).toFixed(2),0,y+3);
  }}
  c.lineWidth=2;c.strokeStyle="#80e9b6";c.beginPath();
  donnees.forEach((v,i)=>{{const x=45+i*(w-48)/Math.max(1,donnees.length-1);
    const y=12+(haut-v)*(h-24)/(haut-bas);i?c.lineTo(x,y):c.moveTo(x,y);}});
  c.stroke();
}}
new ResizeObserver(dessiner).observe(canvas);
</script></main></html>""", encoding="utf-8")
