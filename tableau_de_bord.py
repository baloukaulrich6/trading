"""Petit serveur web local qui affiche l'interface animée et l'état du robot.

Adresse : http://127.0.0.1:8765 (visible seulement depuis ce PC).
Il sert aussi de verrou : si le port est déjà pris, un autre robot tourne déjà.
"""
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from secrets import compare_digest

from pilotage_local import Pilotage

log = logging.getLogger("robot")

PAGE = Path(__file__).resolve().parent / "interface" / "index.html"
RESSOURCES = {
    "/terminal.css": ("terminal.css", "text/css; charset=utf-8"),
    "/terminal.js": ("terminal.js", "text/javascript; charset=utf-8"),
}
INSTANTANE = "{}"   # État public publié par la tâche.
PILOTAGE: Pilotage | None = None


class _Gestionnaire(BaseHTTPRequestHandler):
    def _repondre(self, code: int, contenu: bytes, type_mime: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(contenu)

    def _local(self) -> bool:
        return self.headers.get("Host") in (
            f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"
        )

    def _json(self, code, data):
        self._repondre(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802 (nom imposé par http.server)
        if not self._local():
            self._json(403, {"message": "Accès local uniquement."})
            return
        if self.path == "/api/pilotage" and PILOTAGE is not None:
            self._json(200, {**PILOTAGE.etat(), "jeton": PILOTAGE.jeton})
        elif self.path == "/api/etat":
            self._repondre(200, INSTANTANE.encode("utf-8"), "application/json; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            try:
                self._repondre(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            except OSError:
                self._repondre(500, "interface/index.html introuvable".encode(), "text/plain; charset=utf-8")
        elif self.path in RESSOURCES:
            fichier, mime = RESSOURCES[self.path]
            try:
                self._repondre(200, PAGE.with_name(fichier).read_bytes(), mime)
            except OSError:
                self._repondre(404, b"", mime)
        else:
            self._repondre(404, b"", "text/plain")

    def do_POST(self):
        if self.path != "/api/pilotage" or PILOTAGE is None:
            self._json(404, {"message": "Pilotage indisponible."})
            return
        if (not self._local() or self.headers.get("Origin") != f"http://{self.headers.get('Host')}"
                or not compare_digest(self.headers.get("X-Nkap-Token", "").encode(), PILOTAGE.jeton.encode())):
            self._json(403, {"message": "Demande d’origine invalide."})
            return
        try:
            longueur = int(self.headers.get("Content-Length", "0"))
            if not 0 < longueur <= 256:
                raise ValueError
            demande = json.loads(self.rfile.read(longueur))
            if not isinstance(demande, dict) or not isinstance(demande.get("mode"), str):
                raise ValueError
        except (ValueError, UnicodeError):
            self._json(400, {"message": "Demande invalide."})
            return
        code, message = PILOTAGE.demander(demande["mode"], confirmer_reel=demande.get("confirmer_reel") is True)
        self._json(code, {"message": message, **PILOTAGE.etat()})

    def log_message(self, *args):  # pas de bruit dans les logs
        pass


def demarrer(port: int) -> bool:
    """Lance le serveur en arrière-plan. Renvoie False si le port est déjà utilisé."""
    try:
        serveur = ThreadingHTTPServer(("127.0.0.1", port), _Gestionnaire)
    except OSError:
        return False
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    log.info("Interface disponible sur http://127.0.0.1:%s", serveur.server_port)
    return True
