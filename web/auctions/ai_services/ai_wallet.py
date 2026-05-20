# auctions/services/ai_wallet.py

from django.db import transaction
from django.core.exceptions import ValidationError
from auctions.utils import get_system_wallet
from auctions.models import BidWallet, WalletTransaction


@transaction.atomic
def charge_wallet_for_ai_message(user, companion, conversation=None):
    wallet = BidWallet.objects.select_for_update().get(user=user)

    cost = companion.cost_per_message  # keep as int

    if wallet.credits < cost:
        raise ValidationError("Insufficient credits.")

    platform_wallet = get_system_wallet()

    wallet.credits -= cost
    platform_wallet.credits += cost

    wallet.save(update_fields=["credits"])
    platform_wallet.save(update_fields=["credits"])

    tx = WalletTransaction.objects.create(
        sender=wallet,
        receiver=platform_wallet,
        transaction_type="ai_message",
        amount=cost,  # Django will store as Decimal automatically

    )

    return wallet, tx

@transaction.atomic
def refund_wallet_for_ai_message(user, companion):
    wallet = BidWallet.objects.select_for_update().get(user=user)

    cost = companion.cost_per_message
    wallet.credits += cost
    wallet.save(update_fields=["credits"])

    WalletTransaction.objects.create(
        sender=None,
        receiver=wallet,
        transaction_type="bonus",
        amount=cost,
    )

    return wallet
