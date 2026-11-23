"""Veto de Claude : il peut bloquer un trade, jamais en proposer un."""
import json
import logging
import re

import config as C

log = logging.getLogger("robot")

CONSIGNE = """Tu es le contrôleur de risque d'un robot de trading en graphique journalier.
Tu ne prédis jamais les prix et tu ne proposes jamais de trade.
Des règles déjà testées te soumettent un trade : tu peux seulement l'autoriser ou le bloquer.

Bloque le trade si au moins une condition est vraie :
1. Une annonce économique à fort impact (banque centrale, emploi, inflation, PIB) concerne
   l'une des devises du symbole dans les 2 heures qui suivent l'heure indiquée,
   ou a eu lieu il y a moins d'1 heure.
2. Un événement exceptionnel est en cours : crise, intervention d'une banque centrale,
   marché fermé ou jour férié majeur.
3. Les données transmises sont incohérentes (prix, stop ou volume anormaux).

Sinon, autorise. Utilise la recherche web pour vérifier le calendrier économique du jour.
Termine ta réponse par un objet JSON sur une seule ligne :
{"decision": "autoriser" ou "bloquer", "raison": "phrase courte en français"}"""


def lire_decision_stricte(texte: str) -> tuple[bool, str]:
    """Extrait le dernier objet JSON de la réponse. En cas de doute : bloquer."""
    objets = re.findall(r"\{[^{}]*\}", texte)
    if not objets:
        raise ValueError("réponse de Claude illisible")
    try:
        avis = json.loads(objets[-1])
    except json.JSONDecodeError as erreur:
        raise ValueError("JSON de Claude invalide") from erreur
    decision = str(avis.get("decision", "")).strip().lower()
    raison = avis.get("raison")
    if decision not in ("autoriser", "bloquer") or not isinstance(raison, str) or not raison.strip():
        raise ValueError("décision ou raison manquante dans la réponse de Claude")
    raison = raison.strip()
    return decision == "autoriser", raison


def lire_decision(texte: str) -> tuple[bool, str]:
    try:
        return lire_decision_stricte(texte)
    except ValueError as erreur:
        return False, f"{erreur} : trade bloqué par prudence"


def demander_veto(donnees: dict) -> tuple[bool, str]:
    """Renvoie (autorisé ?, raison). Si Claude ne répond pas : aucun nouveau trade."""
    if not C.CLAUDE_ACTIF:
        return True, "veto de Claude désactivé"
    if not C.ANTHROPIC_API_KEY:
        return False, "clé API Claude absente : aucun nouveau trade"

    try:
        return lire_decision(interroger_claude(donnees))
    except Exception as erreur:  # réseau, clé invalide, quota...
        log.warning("Claude injoignable : %s", erreur)
        return False, "Claude injoignable : aucun nouveau trade aujourd'hui"


def interroger_claude(donnees: dict, *, diagnostic: bool = False) -> str:
    """Appelle le modèle et renvoie le texte brut du veto."""
    import anthropic

    client = anthropic.Anthropic(api_key=C.ANTHROPIC_API_KEY, timeout=60.0)
    options = {
        "system": CONSIGNE,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
    }
    if diagnostic:
        options = {"system": (
            "Contrôle les données fictives. Un volume nul ou négatif doit être bloqué. "
            'Réponds uniquement par un objet JSON avec "decision" ("autoriser" ou "bloquer") '
            'et "raison" (une courte phrase en français).'
        )}
    reponse = client.messages.create(
        model=C.CLAUDE_MODELE,
        max_tokens=1024,
        messages=[{"role": "user", "content": json.dumps(donnees, ensure_ascii=False)}],
        **options,
    )
    texte = "".join(b.text for b in reponse.content if b.type == "text")
    if diagnostic and (not texte.strip() or reponse.stop_reason != "end_turn"):
        blocs = ", ".join(b.type for b in reponse.content) or "aucun"
        raise ValueError(f"réponse texte incomplète (arrêt : {reponse.stop_reason}, blocs : {blocs})")
    return texte
