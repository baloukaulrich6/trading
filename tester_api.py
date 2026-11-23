"""Vérifie MT5 et le veto Claude sur un exemple fictif, sans envoyer d'ordre."""
import argparse
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


def tester_claude(*, avec_recherche: bool = False) -> str:
    if not C.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY est absente de .env")
    exemple = {
        "heure_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "symbole": "EURUSD",
        "sens": "achat",
        "module": "TUR",
        "raison_signal": ("Exemple fictif. Utiliser la recherche web pour vérifier le calendrier, sans ordre."
                         if avec_recherche else "Exemple fictif avec volume nul. Vérifier le veto, sans ordre."),
        "prix": 1.10,
        "stop": 1.09,
        "volume": 0.01 if avec_recherche else 0,
    }
    autorise, raison = lire_decision_stricte(interroger_claude(
        exemple, diagnostic=not avec_recherche, verifier_recherche=avec_recherche
    ))
    if autorise and not avec_recherche:
        raise ValueError("Le modèle a autorisé un volume nul. Le test attend un blocage.")
    if avec_recherche:
        decision = "autoriser" if autorise else "bloquer"
        return f"Claude OK · {C.CLAUDE_MODELE} · recherche web reçue · décision {decision} : {raison}"
    return f"Claude OK · {C.CLAUDE_MODELE} · test sans recherche web · blocage attendu : {raison}"


def diagnostic(*, avec_recherche: bool = False) -> tuple[int, list[str]]:
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
        messages.append(tester_claude(avec_recherche=avec_recherche))
    except Exception as erreur:
        reussi = False
        statut = getattr(erreur, "status_code", None)
        detail = str(erreur) if isinstance(erreur, ValueError) else type(erreur).__name__
        if statut is not None:
            detail += f" (HTTP {statut})"
        messages.append(f"Claude ÉCHEC · {C.CLAUDE_MODELE} · {detail}")
    return (0 if reussi else 1), messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--avec-recherche", action="store_true",
                        help="Teste aussi la recherche web de Claude, sans ordre")
    args = parser.parse_args()
    code, messages = diagnostic(avec_recherche=args.avec_recherche)
    print("\n".join(messages))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
