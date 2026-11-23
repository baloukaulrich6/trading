"""Sélection du compte pour la tâche locale. Le choix s'applique au prochain passage."""
import os
from secrets import token_urlsafe
from threading import Event, Lock


class Pilotage:
    def __init__(self) -> None:
        self.jeton = token_urlsafe(32)
        self.reveil = Event()
        self._verrou = Lock()
        self._demande = "TEST"
        self._applique = "TEST"
        self.demo = self._lire_demo()

    @staticmethod
    def _lire_demo() -> dict | None:
        login = os.getenv("HFM_DEMO_LOGIN", "").strip()
        serveur = os.getenv("HFM_DEMO_SERVEUR", "").strip()
        if not login.isascii() or not login.isdigit() or int(login) <= 0 or not serveur:
            return None
        return {
            "nom": "HFM", "login": int(login), "serveur": serveur,
            "mot_de_passe": os.getenv("HFM_DEMO_MOT_DE_PASSE", ""),
            "chemin": os.getenv("HFM_DEMO_CHEMIN", "") or os.getenv("HFM_CHEMIN", ""),
            "demo_uniquement": True,
        }

    def etat(self) -> dict:
        with self._verrou:
            return {"demande": self._demande, "applique": self._applique,
                    "demo_disponible": self.demo is not None, "reel_disponible": False,
                    "raison_reel": "Validation hors échantillon et semaine en démo encore requises."}

    def demander(self, choix: str) -> tuple[int, str]:
        with self._verrou:
            if choix == "REEL":
                return 409, "Réel verrouillé : backtest, réserve et semaine en démo requis."
            if choix == "DEMO" and self.demo is None:
                return 409, "Renseigne HFM_DEMO_LOGIN et HFM_DEMO_SERVEUR dans .env, puis relance la tâche."
            if choix not in ("TEST", "DEMO"):
                return 400, "Mode inconnu."
            self._demande = choix
            self.reveil.set()
            return 200, "Choix enregistré pour le prochain passage."

    def appliquer(self) -> str:
        with self._verrou:
            self._applique = self._demande
            self.reveil.clear()
            return self._applique
