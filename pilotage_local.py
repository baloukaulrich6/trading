"""Sélection du compte pour la tâche locale. Le choix s'applique au prochain passage."""
import os
from secrets import token_urlsafe
from threading import Event, Lock


class Pilotage:
    def __init__(self, hfm_reel: dict | None = None) -> None:
        self.jeton = token_urlsafe(32)
        self.reveil = Event()
        self._verrou = Lock()
        self._demande = "TEST"
        self._applique = "TEST"
        self.demo = self._lire_demo()
        self.reel = (
            {**hfm_reel, "reel_uniquement": True, "reel_confirme": True}
            if hfm_reel and hfm_reel["login"] and hfm_reel["serveur"] else None
        )

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
                    "demo_disponible": self.demo is not None, "reel_disponible": self.reel is not None}

    def demander(self, choix: str, *, confirmer_reel: bool = False) -> tuple[int, str]:
        with self._verrou:
            if choix == "REEL":
                if self.reel is None:
                    return 409, "Renseigne le compte HFM réel dans .env, puis relance la tâche."
                if not confirmer_reel:
                    return 409, "Confirme explicitement le passage en réel."
            if choix == "DEMO" and self.demo is None:
                return 409, "Renseigne HFM_DEMO_LOGIN et HFM_DEMO_SERVEUR dans .env, puis relance la tâche."
            if choix not in ("TEST", "DEMO", "REEL"):
                return 400, "Mode inconnu."
            self._demande = choix
            self.reveil.set()
            return 200, "Choix enregistré pour le prochain passage."

    def appliquer(self) -> str:
        with self._verrou:
            self._applique = self._demande
            self.reveil.clear()
            return self._applique
