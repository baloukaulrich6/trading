"""Réglages du robot. Les secrets (mots de passe, clé API) sont lus dans le fichier .env."""
import os

from dotenv import load_dotenv

load_dotenv()


def _oui(nom, defaut="non"):
    return os.getenv(nom, defaut).strip().lower() in ("oui", "yes", "true", "1")


# TEST : observation. ORDRES : exécution, soumise à la confirmation du compte réel.
MODE = os.getenv("MODE", "TEST").strip().upper()
if MODE in ("LIVE", "REEL", "RÉEL"):
    MODE = "ORDRES"
if MODE not in ("TEST", "ORDRES"):
    raise ValueError("MODE doit être TEST ou ORDRES (LIVE est un alias).")

# Délai maximal de connexion à MetaTrader 5, en millisecondes.
MT5_TIMEOUT_MS = int(os.getenv("MT5_TIMEOUT_MS", "").strip() or "60000")
if MT5_TIMEOUT_MS <= 0:
    raise ValueError("MT5_TIMEOUT_MS doit être un entier positif en millisecondes.")

# Marchés suivis (noms de base, le suffixe du courtier est trouvé automatiquement)
SYMBOLES = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]

# Gestion du risque
RISQUE_PAR_TRADE = 0.01      # 1 % du capital par trade
MAX_POSITIONS = 4            # positions ouvertes au maximum par courtier
SEUIL_ARRET = 0.80           # arrêt des nouveaux trades si le capital tombe sous 80 % du départ

# Module Turtles (canaux de Donchian)
TURTLES_ENTREE = 20          # cassure du plus haut / plus bas de 20 jours
TURTLES_SORTIE = 10          # sortie sur le plus bas / plus haut de 10 jours
ATR_PERIODE = 20             # N = ATR sur 20 jours
STOP_EN_N = 2.0              # stop à 2N

# Détecteur de régime (Even Better Sinewave d'Ehlers)
EBSW_DUREE = 40
EBSW_LISSAGE = 10
SEUIL_TENDANCE = 0.85        # |EBSW| >= 0,85 : tendance, sinon : cycle

# Module contrarien (mode cycle uniquement)
RSI_PERIODE = 2
RSI_ACHAT = 10
RSI_VENTE = 90
SMA_LONGUE = 200
SMA_SORTIE = 5

# Identifiant des ordres du robot dans MT5
MAGIC = 20261121

# Courtiers : un terminal MT5 installé dans un dossier séparé pour chacun
COURTIERS = [
    {
        "nom": "EXNESS",
        "actif": _oui("EXNESS_ACTIF", "oui"),
        "login": int(os.getenv("EXNESS_LOGIN", "0") or 0),
        "mot_de_passe": os.getenv("EXNESS_MOT_DE_PASSE", ""),
        "serveur": os.getenv("EXNESS_SERVEUR", ""),
        "chemin": os.getenv("EXNESS_CHEMIN", ""),
    },
    {
        "nom": "HFM",
        "actif": _oui("HFM_ACTIF", "non"),
        "login": int(os.getenv("HFM_LOGIN", "0") or 0),
        "mot_de_passe": os.getenv("HFM_MOT_DE_PASSE", ""),
        "serveur": os.getenv("HFM_SERVEUR", ""),
        "chemin": os.getenv("HFM_CHEMIN", ""),
    },
]

# Claude : simple droit de veto, jamais de décision d'achat ou de vente
CLAUDE_ACTIF = _oui("CLAUDE_ACTIF", "oui")
CLAUDE_MODELE = os.getenv("CLAUDE_MODELE", "claude-haiku-5-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Fichiers produits par le robot
FICHIER_ETAT = "etat.json"
FICHIER_JOURNAL = "journal.csv"
FICHIER_LOG = "robot.log"
