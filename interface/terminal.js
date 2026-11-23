"use strict";

const $ = (id) => document.getElementById(id);
const temps = new Intl.DateTimeFormat("fr-FR", {
  timeZone: "Africa/Douala", hour: "2-digit", minute: "2-digit", second: "2-digit"
});
const dateCourte = new Intl.DateTimeFormat("fr-FR", { timeZone: "Africa/Douala", day: "2-digit", month: "2-digit" });
const format = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtPrix = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 6, minimumFractionDigits: 2 });
const argent = (v, devise = "") => Number.isFinite(v) ? [format.format(v), devise].filter(Boolean).join(" ") : "—";
const gain = (v, devise) => Number.isFinite(v) ? (v > 0 ? "+" : "") + argent(v, devise) : "—";
const prix = (v) => Number.isFinite(v) ? fmtPrix.format(v) : "—";
const cleMarche = (m) => m.courtier + "/" + m.marche;
const signes = { achat: "positif", vente: "negatif" };
const etatsMode = { TEST: "Observation", DEMO: "Démo", REEL: "Réel" };

let etat = {};
let jeton = null;
let marcheChoisi = "";
let periode = 20;
let pointeur = null;
let graphique = null;
let signatureMarches = "";
let signatureJournal = "";

function noeud(balise, texte = "", classe = "") {
  const element = document.createElement(balise);
  if (texte) element.textContent = texte;
  if (classe) element.className = classe;
  return element;
}

function marcheActif() {
  const marches = etat.marches || [];
  return marches.find((m) => cleMarche(m) === marcheChoisi) || marches[0];
}

function compteActif() {
  return etat.courtiers?.[marcheActif()?.courtier] || Object.values(etat.courtiers || {})[0];
}

function montrerCompte() {
  const c = compteActif();
  const devise = c?.devise;
  const t = etat.risque_pct;
  const a = c?.objectif;
  const nom = marcheActif()?.courtier || Object.keys(etat.courtiers || {})[0];
  $("contexte").textContent = c
    ? [nom, c.reel ? "Compte réel" : "Compte démo", c.serveur].filter(Boolean).join(" · ")
    : etat.maj ? etat.message || "Aucun compte connecté" : "En attente du relevé MT5";
  $("capital").textContent = argent(c?.capital, devise);
  $("equivalent").textContent = Number.isFinite(c?.solde)
    ? "Solde : " + argent(c.solde, devise) : "";
  if (devise === "USC" && Number.isFinite(c?.capital)) {
    $("equivalent").textContent = [$("equivalent").textContent, "Capital : " + argent(c.capital / 100, "USD")]
      .filter(Boolean).join(" · ");
  }
  $("jour").textContent = gain(c?.resultat_jour, devise);
  $("jour").className = c?.resultat_jour > 0 ? "positif" : c?.resultat_jour < 0 ? "negatif" : "";
  $("semaine").textContent = c ? "Semaine : " + gain(c.resultat_semaine, devise) : "";
  const positions = c?.positions || [];
  $("nombre-positions").textContent = c ? String(positions.length) : "—";
  const latent = positions.reduce((somme, p) => somme + p.resultat, 0);
  $("executions").textContent = c ? [
    "Latent : " + gain(latent, devise),
    Number.isFinite(c.transactions) ? c.transactions + " exécution(s) du jour" : ""
  ].filter(Boolean).join(" · ") : "";
  $("budget").textContent = argent(c?.capital * t / 100, devise);
  $("levier").textContent = [Number.isFinite(t) ? format.format(t) + " % du capital" : "",
    Number.isFinite(c?.marge_libre) ? "Marge libre : " + argent(c.marge_libre, devise) : ""].filter(Boolean).join(" · ");
  $("objectif").hidden = !a;
  $("objectif").textContent = a
    ? [argent(a.solde_usd, "USD") + " / " + argent(a.cible_usd, "USD"),
      "échéance " + a.date_fin + " (Douala)", a.motif].filter(Boolean).join(" · ") : "";

  const bloc = $("positions");
  if (!positions.length) {
    bloc.replaceChildren(noeud("p", c ? "Aucune position ouverte du robot." : "Données de position indisponibles.", "vide"));
    return;
  }
  const table = noeud("table", "", "chiffres");
  const titres = table.createTHead().insertRow();
  ["Marché / ticket", "Sens", "Lots", "Entrée", "Stop", "Latent"].forEach((titre) => titres.append(noeud("th", titre)));
  const corps = table.createTBody();
  for (const p of positions) {
    const ligne = corps.insertRow();
    [p.symbole + (p.ticket != null ? " #" + p.ticket : ""), p.sens, p.volume,
      prix(p.prix), p.stop > 0 ? prix(p.stop) : "—", gain(p.resultat, devise)].forEach((v, i) => {
      const cellule = ligne.insertCell();
      cellule.textContent = v ?? "—";
      if (i === 5) cellule.className = p.resultat > 0 ? "positif" : p.resultat < 0 ? "negatif" : "";
    });
  }
  bloc.replaceChildren(table);
}

function montrerMarches() {
  const marches = etat.marches || [];
  const actif = marcheActif();
  marcheChoisi = actif ? cleMarche(actif) : "";
  $("nombre-marches").textContent = marches.length ? marches.length + " instruments · Dernier bid MT5" : "Marchés MT5";
  const signature = JSON.stringify([marcheChoisi, marches.map((m) => [cleMarche(m), m.bid, m.statut])]);
  if (signature === signatureMarches) return;
  signatureMarches = signature;
  const conteneur = $("liste-marches");
  const focus = conteneur.contains(document.activeElement) ? document.activeElement.dataset.marche : null;
  conteneur.replaceChildren(...(marches.length ? marches.map((m) => {
    const cle = cleMarche(m);
    const bouton = noeud("button", "", "marche");
    bouton.type = "button";
    bouton.dataset.marche = cle;
    bouton.setAttribute("aria-pressed", String(cle === marcheChoisi));
    const label = noeud("span");
    label.append(noeud("strong", m.symbole || m.marche), noeud("small", m.courtier || ""));
    const dernier = m.bougies?.at(-1);
    const montant = noeud("span", prix(m.bid ?? dernier?.[4]), "chiffres");
    if (!Number.isFinite(m.bid) && dernier) montant.append(noeud("small", "Clôture"));
    const signal = noeud("span", m.statut === "achat" ? "Achat" : m.statut === "vente" ? "Vente" : m.statut || "—", "signal");
    signal.dataset.ton = signes[m.statut] || "";
    bouton.append(label, montant, signal);
    bouton.addEventListener("click", () => {
      marcheChoisi = cle;
      pointeur = null;
      montrerMarches();
      montrerCompte();
      dessiner();
    });
    return bouton;
  }) : [noeud("p", "En attente des symboles MT5.", "vide")]));
  if (focus) [...conteneur.querySelectorAll("button")].find((b) => b.dataset.marche === focus)?.focus();
}

function classification(e) {
  const resultat = (e.resultat || "").toLowerCase();
  const action = (e.action || "").toLowerCase();
  if ((action === "entrée" || action === "sortie") && resultat === "ok") {
    return [action === "entrée" ? "Entrée exécutée" : "Sortie exécutée", "positif", "execution"];
  }
  if (e.mode === "TEST" && (action === "entrée" || action === "sortie") && resultat === "non envoyé") {
    return ["Simulation · non envoyé", "", "test"];
  }
  if (action === "veto" || e.type === "veto") return ["Veto Claude", "attention", "blocages"];
  if (action === "refus taille") return ["Risque hors limite", "attention", "blocages"];
  if (action === "objectif") return ["Arrêt objectif", "attention", "blocages"];
  if (resultat === "non envoyé") return ["Ordre non envoyé", "negatif", "blocages"];
  return [action || "Décision", "", e.mode === "TEST" ? "test" : "info"];
}

function montrerJournal() {
  const filtre = $("filtre").value;
  const evenements = etat.evenements || [];
  const signature = JSON.stringify([filtre, evenements]);
  if (signature === signatureJournal) return;
  signatureJournal = signature;
  const journal = $("journal");
  const ouverts = new Set([...journal.querySelectorAll("details[open]")].map((x) => x.dataset.cle));
  const lignes = evenements.map((e, i) => [e, i, classification(e)]).filter(([e, , categorie]) =>
    filtre === "all" || (filtre === "test" ? e.mode === "TEST" : categorie[2] === filtre));
  if (!lignes.length) {
    journal.replaceChildren(noeud("p", filtre === "execution" ? "Aucune exécution dans le journal récent." : "Aucune décision à afficher.", "vide"));
    return;
  }
  journal.replaceChildren(...lignes.map(([e, i, [libelle, ton]]) => {
    const details = noeud("details");
    details.dataset.cle = [e.heure, e.titre, e.detail, i].join("|");
    details.open = ouverts.has(details.dataset.cle);
    const resume = noeud("summary");
    const instant = typeof e.heure === "string" && e.heure
      ? new Date(e.heure.includes("T") ? e.heure : e.heure.replace(" ", "T") + ":00Z") : null;
    const heure = instant && Number.isFinite(instant.valueOf())
      ? dateCourte.format(instant) + " " + temps.format(instant).slice(0, 5) : e.heure || "—";
    const horodatage = noeud("time", heure);
    horodatage.title = "Heure de Douala";
    const marche = noeud("strong", e.symbole || e.courtier || "—");
    const statut = noeud("span", libelle, "pastille");
    statut.dataset.ton = ton;
    resume.append(horodatage, marche, statut, noeud("span", e.mode || "—", "type-mode"));
    details.append(resume, noeud("p", [e.courtier, e.detail || e.titre].filter(Boolean).join(" · "), "detail"));
    return details;
  }));
}

function dessiner() {
  const m = marcheActif();
  const canvas = $("cours");
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const { width, height } = canvas.getBoundingClientRect();
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  ctx.scale(ratio, ratio);
  const bougies = (m?.bougies || []).slice(-periode);
  $("symbole").textContent = m ? (m.symbole || m.marche) + " · D1" : "Graphique D1";
  const tick = Number.isFinite(m?.bid) && Number.isFinite(m?.ask)
    ? "Bid " + prix(m.bid) + "  /  Ask " + prix(m.ask) : "";
  const heureTick = Number.isFinite(m?.tick_utc) && m.tick_utc > 0
    ? " Dernier tick " + dateCourte.format(new Date(m.tick_utc * 1000)) + " "
      + temps.format(new Date(m.tick_utc * 1000)) : "";
  $("detail-cours").textContent = tick ? tick + " ·" + (heureTick || " cotation MT5") : "Bougies journalières clôturées";
  $("vide-cours").hidden = bougies.length > 0;
  $("vide-cours").textContent = m ? "Aucune bougie reçue pour cet instrument." : "Les cours s’afficheront après le premier relevé MT5.";
  $("lecture-cours").textContent = "";
  graphique = null;
  if (!bougies.length || width < 120) return;

  const gauche = 16, haut = 16, droite = width - 70, bas = height - 31;
  const cols = Math.max(1, bougies.length);
  const pas = (droite - gauche) / cols;
  const largeurBougie = Math.max(1, Math.min(11, pas * .55));
  const maxi = Math.max(...bougies.map((b) => b[2]));
  const mini = Math.min(...bougies.map((b) => b[3]));
  const marge = (maxi - mini) * .09 || maxi * .005;
  const maximum = maxi + marge, minimum = mini - marge;
  const y = (v) => haut + (maximum - v) * (bas - haut) / (maximum - minimum);
  const x = (i) => gauche + (i + .5) * pas;
  graphique = { gauche, pas, nombre: cols };

  ctx.font = "11px Segoe UI, sans-serif";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= 5; i++) {
    const niveau = haut + (bas - haut) * i / 5;
    ctx.strokeStyle = "#28323b";
    ctx.beginPath(); ctx.moveTo(gauche, niveau); ctx.lineTo(droite, niveau); ctx.stroke();
    ctx.fillStyle = "#a8b4bf";
    ctx.fillText(prix(maximum - (maximum - minimum) * i / 5), droite + 8, niveau);
  }
  const actifs = Math.min(width < 440 ? 3 : 6, cols);
  for (let j = 0; j < actifs; j++) {
    const i = Math.round(j * (cols - 1) / Math.max(1, actifs - 1));
    const label = bougies[i][0].slice(5).split("-").reverse().join("/");
    ctx.fillText(label, Math.max(gauche, x(i) - 14), bas + 16);
  }
  bougies.forEach(([date, ouverture, hautCours, basCours, cloture], i) => {
    const couleur = cloture >= ouverture ? "#68d3a4" : "#ef8980";
    ctx.strokeStyle = couleur;
    ctx.fillStyle = couleur;
    ctx.beginPath(); ctx.moveTo(x(i), y(hautCours)); ctx.lineTo(x(i), y(basCours)); ctx.stroke();
    ctx.fillRect(x(i) - largeurBougie / 2, Math.min(y(ouverture), y(cloture)),
      largeurBougie, Math.max(1, Math.abs(y(ouverture) - y(cloture))));
  });
  const indice = pointeur == null ? cols - 1 : Math.min(cols - 1, pointeur);
  if (pointeur != null) {
    ctx.strokeStyle = "#a8b4bf";
    ctx.setLineDash([3, 4]);
    ctx.beginPath(); ctx.moveTo(x(indice), haut); ctx.lineTo(x(indice), bas); ctx.stroke();
    ctx.setLineDash([]);
  }
  const [date, ouverture, hautCours, basCours, cloture] = bougies[indice];
  $("lecture-cours").textContent = date + " · O " + prix(ouverture) + " · H " + prix(hautCours)
    + " · B " + prix(basCours) + " · C " + prix(cloture);
}

$("cours").addEventListener("pointermove", (e) => {
  if (!graphique) return;
  const indice = Math.floor((e.offsetX - graphique.gauche) / graphique.pas);
  const nouveau = indice >= 0 && indice < graphique.nombre ? indice : null;
  if (nouveau !== pointeur) { pointeur = nouveau; dessiner(); }
});
$("cours").addEventListener("pointerleave", () => { pointeur = null; dessiner(); });
new ResizeObserver(dessiner).observe($("cours"));
for (const bouton of document.querySelectorAll("[data-periode]")) {
  bouton.addEventListener("click", () => {
    periode = Number(bouton.dataset.periode);
    pointeur = null;
    document.querySelectorAll("[data-periode]").forEach((b) => b.setAttribute("aria-pressed", String(b === bouton)));
    dessiner();
  });
}
$("filtre").addEventListener("change", montrerJournal);

function afficher(frais) {
  const connectes = Object.values(etat.courtiers || {}).some((c) => c.connecte);
  $("voyant").dataset.etat = frais && connectes ? "ok" : "off";
  $("connexion").textContent = frais ? connectes ? "MT5 connecté" : "MT5 en attente" : "Relevé indisponible";
  const reel = frais && etat.mode === "ORDRES" && etat.compte_reel && etat.ordres_autorises;
  $("mode").textContent = !frais ? "État non confirmé" : reel ? "Ordres réels activés"
    : etat.mode === "ORDRES" ? etat.ordres_autorises ? "Démo" : "Envoi indisponible" : "Observation";
  $("mode").dataset.ton = reel ? "negatif" : frais ? "" : "attention";
  $("fenetre").textContent = frais && typeof etat.entrees_ouvertes === "boolean"
    ? "Entrées " + (etat.entrees_ouvertes ? "ouvertes" : "fermées") + " · " + etat.heure_entree + "–" + etat.heure_limite
    : "";
  $("veto").textContent = frais ? "Claude : " + (etat.veto_claude ? "veto actif" : "veto désactivé") : "";
  $("maj").textContent = etat.maj ? "Dernier relevé " + temps.format(new Date(etat.maj)) + " · Douala" : "";
  montrerMarches();
  montrerCompte();
  montrerJournal();
  dessiner();
  $("fantome").hidden = !Array.isArray(etat.fantome);
  $("observations").replaceChildren(...(etat.fantome || []).map((o) =>
    noeud("p", [o.marche, o.version, o.signal || "Aucun signal", o.module].filter(Boolean).join(" · "), "vide")
  ));
  if (!frais && etat.maj) $("contexte").textContent += " · Données du dernier relevé";
}

async function rafraichir() {
  try {
    const reponse = await fetch("/api/etat", { cache: "no-store" });
    if (!reponse.ok) throw new Error();
    etat = await reponse.json();
    const date = Date.parse(etat.maj);
    afficher(Number.isFinite(date) && Date.now() - date < 45000);
  } catch {
    afficher(false);
  }
}

async function lirePilotage() {
  try {
    const reponse = await fetch("/api/pilotage", { cache: "no-store" });
    if (!reponse.ok) throw new Error();
    const p = await reponse.json();
    jeton = p.jeton;
    $("pilotage").hidden = false;
    document.querySelectorAll("[data-mode]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.mode === p.applique))
    );
    if (p.demande !== p.applique) $("message-pilotage").textContent = "Passage en " + etatsMode[p.demande] + " en attente.";
    return p;
  } catch {
    jeton = null;
    $("pilotage").hidden = true;
    return null;
  }
}

for (const bouton of document.querySelectorAll("[data-mode]")) {
  bouton.addEventListener("click", async () => {
    const p = await lirePilotage();
    if (!p) return;
    const mode = bouton.dataset.mode;
    if (mode === p.applique && mode === p.demande) {
      $("message-pilotage").textContent = "Mode " + etatsMode[mode] + " déjà appliqué.";
      return;
    }
    const confirmerReel = mode === "REEL" && p.reel_disponible &&
      window.confirm("Passer Nkap en réel sur HFM ? Le robot pourra engager ton argent.");
    if (mode === "REEL" && p.reel_disponible && !confirmerReel) return;
    const boutons = [...document.querySelectorAll("[data-mode]")];
    boutons.forEach((b) => { b.disabled = true; });
    try {
      const reponse = await fetch("/api/pilotage", {
        method: "POST", headers: { "Content-Type": "application/json", "X-Nkap-Token": jeton },
        body: JSON.stringify({ mode, confirmer_reel: confirmerReel })
      });
      const choix = await reponse.json();
      $("message-pilotage").textContent = choix.message;
      await lirePilotage();
    } catch {
      $("message-pilotage").textContent = "Le service local ne répond pas.";
    } finally {
      boutons.forEach((b) => { b.disabled = false; });
    }
  });
}

rafraichir();
lirePilotage();
setInterval(rafraichir, 4000);
setInterval(lirePilotage, 4000);
