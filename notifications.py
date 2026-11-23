"""Envoi des messages Telegram (sans bibliothèque supplémentaire).

Mise en place, une seule fois :
1. Dans Telegram, écris à @BotFather, tape /newbot et suis les étapes : il te donne un TOKEN.
2. Mets TELEGRAM_TOKEN=... dans .env.
3. Envoie « bonjour » à ton nouveau bot, puis lance : python notifications.py
   Le script affiche ton TELEGRAM_CHAT_ID : copie-le dans .env.
"""
import html
import json
import logging
import os
import urllib.parse
import urllib.request

import config  # Charge le fichier .env du robot.

log = logging.getLogger("robot")
API = "https://api.telegram.org/bot{token}/{methode}"


def _appel(methode: str, donnees: dict | None = None) -> dict:
    url = API.format(token=os.getenv("TELEGRAM_TOKEN", ""), methode=methode)
    corps = urllib.parse.urlencode(donnees).encode() if donnees else None
    with urllib.request.urlopen(url, data=corps, timeout=15) as reponse:
        resultat = json.loads(reponse.read().decode())
        if not resultat.get("ok"):
            raise RuntimeError("Réponse Telegram refusée")
        return resultat


def echapper(texte) -> str:
    """Protège les caractères spéciaux du HTML de Telegram (<, >, &)."""
    return html.escape(str(texte), quote=False)


def envoyer(texte: str) -> bool:
    """Envoie un message (HTML simple : <b>, <i>, <code>). Ne plante jamais le robot."""
    if not active():
        return False
    try:
        _appel("sendMessage", {"chat_id": os.getenv("TELEGRAM_CHAT_ID", ""), "text": texte[:4000],
                               "parse_mode": "HTML", "disable_web_page_preview": "true"})
        return True
    except Exception as erreur:
        log.warning("Telegram : envoi impossible (%s)", type(erreur).__name__)
        return False


def active() -> bool:
    return bool(os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


if __name__ == "__main__":
    if not os.getenv("TELEGRAM_TOKEN", ""):
        raise SystemExit("Ajoute d'abord TELEGRAM_TOKEN=... dans .env (donné par @BotFather).")
    try:
        messages = _appel("getUpdates").get("result", [])
    except Exception as erreur:
        raise SystemExit(f"Lecture Telegram impossible ({type(erreur).__name__}).") from None
    discussions = {m["message"]["chat"]["id"]: m["message"]["chat"].get("first_name", "")
                   for m in messages if "message" in m}
    if not discussions:
        print("Aucun message reçu : envoie « bonjour » à ton bot dans Telegram, puis relance.")
    for identifiant, prenom in discussions.items():
        print(f"TELEGRAM_CHAT_ID={identifiant}   ({prenom})")
