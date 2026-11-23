"""Bilans du robot à partir des transactions enregistrées par MT5."""
from datetime import timedelta, timezone

DOUALA = timezone(timedelta(hours=1), "Douala")


def debut_jour(maintenant):
    return maintenant.astimezone(DOUALA).replace(hour=0, minute=0, second=0, microsecond=0)


def debut_semaine(maintenant):
    jour = debut_jour(maintenant)
    return jour - timedelta(days=jour.weekday())


def montant_transaction(deal):
    return deal.profit + deal.commission + deal.swap + deal.fee


def bilan(transactions, magic):
    if transactions is None:
        return None, None
    montants = [montant_transaction(deal) for deal in transactions if deal.magic == magic]
    return sum(montants), len(montants)
