"""Vérifie MT5 et le veto Claude sur un exemple fictif, sans envoyer d'ordre."""
from datetime import datetime, timezone

import config as C
from courtier import Courtier
from veto_claude import interroger_claude, lire_decision_stricte


def tester_mt5(conf: dict) -> str:
    courtier = Courtier(conf)
    courtier.connecter()
    try:
        compte = courtier.infos_compte()
        if compte is None:
            raise RuntimeError("Informations du compte indisponibles")
        for base in C.SYMBOLES:
            symbole = courtier.trouver_symbole(base)
            if symbole is not None:
                bougie = courtier.bougies(symbole, 1).iloc[-1]
                return (f"MT5 OK · {courtier.nom} · {compte.equity:.2f} {compte.currency} · "
                        f"{symbole} D1 {bougie.name:%Y-%m-%d} : clôture {bougie['close']}")
        raise RuntimeError("Aucun symbole configuré accessible")
    finally:
        courtier.deconnecter()


def tester_claude() -> str:
    if not C.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY est absente de .env")
    exemple = {
        "heure_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "symbole": "EURUSD",
        "sens": "achat",
        "module": "TUR",
        "raison_signal": "Exemple fictif avec volume nul. Vérifier le veto, sans ordre.",
        "prix": 1.10,
        "stop": 1.09,
        "volume": 0,
    }
    autorise, raison = lire_decision_stricte(interroger_claude(exemple, diagnostic=True))
    if autorise:
        raise ValueError("Le modèle a autorisé un volume nul. Le test attend un blocage.")
    return f"Claude OK · {C.CLAUDE_MODELE} · test sans recherche web · blocage attendu : {raison}"


def diagnostic() -> tuple[int, list[str]]:
    messages = []
    actifs = [conf for conf in C.COURTIERS if conf["actif"]]
    reussi = bool(actifs)
    if not actifs:
        messages.append("MT5 indisponible · Aucun courtier actif dans .env")
    for conf in actifs:
        try:
            messages.append(tester_mt5(conf))
        except (OSError, RuntimeError, ValueError) as erreur:
            reussi = False
            messages.append(f"MT5 ÉCHEC · {conf['nom']} · {erreur}")
    try:
        messages.append(tester_claude())
    except Exception as erreur:
        reussi = False
        statut = getattr(erreur, "status_code", None)
        detail = str(erreur) if isinstance(erreur, ValueError) else type(erreur).__name__
        if statut is not None:
            detail += f" (HTTP {statut})"
        messages.append(f"Claude ÉCHEC · {C.CLAUDE_MODELE} · {detail}")
    return (0 if reussi else 1), messages


def main() -> int:
    code, messages = diagnostic()
    print("\n".join(messages))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
