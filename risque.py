"""Taille de position à 1 % de risque et arrêt automatique en cas de grosse perte."""
import json
import math
import os

import config as C


def taille_position(capital: float, distance_stop: float, info, *,
                    perte_par_lot: float | None = None) -> tuple[float, str]:
    """Volume en lots pour perdre au plus RISQUE_PAR_TRADE du capital si le stop est touché.

    `info` = mt5.symbol_info(symbole). Fonctionne pour les comptes standard ET cent,
    car la valeur du tick est donnée dans la devise du compte (USD ou USC).
    """
    if distance_stop <= 0 or info.volume_step <= 0:
        return 0.0, "données du symbole invalides"

    if perte_par_lot is None:
        if info.trade_tick_size <= 0 or info.trade_tick_value <= 0:
            return 0.0, "données du symbole invalides"
        perte_par_lot = distance_stop / info.trade_tick_size * info.trade_tick_value
    if not math.isfinite(perte_par_lot) or perte_par_lot <= 0:
        return 0.0, "perte au stop indisponible"
    risque_max = capital * C.RISQUE_PAR_TRADE
    pas = info.volume_step

    volume = math.floor(risque_max / perte_par_lot / pas) * pas
    decimales = max(0, -int(math.floor(math.log10(pas))))
    volume = round(min(volume, info.volume_max), decimales)

    if volume < info.volume_min:
        perte_mini = info.volume_min * perte_par_lot
        return 0.0, (f"position minimale trop risquée : {perte_mini:.2f} de perte possible "
                     f"pour {risque_max:.2f} autorisés")
    return volume, "ok"


def _lire_etat() -> dict:
    if os.path.exists(C.FICHIER_ETAT):
        with open(C.FICHIER_ETAT, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _ecrire_etat(etat: dict) -> None:
    with open(C.FICHIER_ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, indent=2)


def arret_urgence(nom_courtier: str, capital: float) -> tuple[bool, str]:
    """Bloque les nouveaux trades si le capital a perdu plus de 20 % depuis le départ."""
    if capital <= 0:
        return True, "compte vide"

    etat = _lire_etat()
    depart = etat.get(nom_courtier, {}).get("capital_depart")
    if depart is None:
        etat[nom_courtier] = {"capital_depart": capital}
        _ecrire_etat(etat)
        return False, f"capital de départ enregistré : {capital:.2f}"

    if capital < depart * C.SEUIL_ARRET:
        return True, (f"capital {capital:.2f} sous {C.SEUIL_ARRET:.0%} du départ ({depart:.2f}). "
                      f"Analyse, puis supprime etat.json pour relancer.")
    return False, "ok"
