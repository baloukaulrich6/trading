"""Petit serveur web local qui affiche l'interface animée et l'état du robot.

Adresse : http://127.0.0.1:8765 (visible seulement depuis ce PC).
Il sert aussi de verrou : si le port est déjà pris, un autre robot tourne déjà.
"""
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("robot")

PAGE = Path(__file__).resolve().parent / "interface" / "index.html"
INSTANTANE = "{}"   # état public du robot, mis à jour par automate.py


class _Gestionnaire(BaseHTTPRequestHandler):
    def _repondre(self, code: int, contenu: bytes, type_mime: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(contenu)

    def do_GET(self):  # noqa: N802 (nom imposé par http.server)
        if self.path == "/api/etat":
            self._repondre(200, INSTANTANE.encode("utf-8"), "application/json; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            try:
                self._repondre(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            except OSError:
                self._repondre(500, "interface/index.html introuvable".encode(), "text/plain; charset=utf-8")
        else:
            self._repondre(404, b"", "text/plain")

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
