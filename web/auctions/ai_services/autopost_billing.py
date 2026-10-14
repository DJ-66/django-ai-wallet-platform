"""Atomic, idempotent FANZ AutoPost Pro credit billing."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auctions.models import (
    AutoPostEntitlement,
    BidWallet,
    WalletTransaction,
)
from auctions.utils import get_system_wallet


SUBSCRIPTION_PRICE = 150
SUBSCRIPTION_DURATION = timedelta(days=30)


@transaction.atomic
def purchase_autopost_subscription(*, account, period_key):
    """Charge once for a unique account billing period."""

    if not account.is_active:
        raise ValidationError("Inactive accounts cannot subscribe.")

    if not isinstance(period_key, str) or not period_key.strip():
        raise ValidationError("A billing-period key is required.")

    if len(period_key) > 80:
        raise ValidationError("Billing-period key is too long.")

    reference = f"autopost:paid:{account.pk}:{period_key}"

    # Ensure the platform wallet exists before acquiring row locks.
    system_wallet = get_system_wallet()
    customer_wallet = BidWallet.objects.get(user=account)

    if customer_wallet.pk == system_wallet.pk:
        raise ValidationError("System wallet cannot purchase AutoPost.")

    # Lock accounts in deterministic primary-key order.
    # Keep the customer lock until the transaction completes.
    locked_wallets = {}
    for wallet_id in sorted((customer_wallet.pk, system_wallet.pk)):
        locked_wallets[wallet_id] = (
            BidWallet.objects.select_for_update().get(pk=wallet_id)
        )

    wallet = locked_wallets[customer_wallet.pk]
    platform_wallet = locked_wallets[system_wallet.pk]

    existing = AutoPostEntitlement.objects.filter(
        reference=reference,
        account=account,
        source=AutoPostEntitlement.SOURCE_PAID,
    ).first()

    if existing is not None:
        return existing, False

    if wallet.credits < SUBSCRIPTION_PRICE:
        raise ValidationError("Insufficient credits for AutoPost Pro.")

    # Do not permit this account to purchase another overlapping period.
    now = timezone.now()
    if AutoPostEntitlement.objects.filter(
        account=account,
        revoked_at__isnull=True,
        starts_at__lte=now,
        expires_at__gt=now,
    ).exists():
        raise ValidationError("An active AutoPost entitlement already exists.")

    wallet.credits -= SUBSCRIPTION_PRICE
    platform_wallet.credits += SUBSCRIPTION_PRICE

    wallet.save(update_fields=["credits"])
    platform_wallet.save(update_fields=["credits"])

    payment = WalletTransaction.objects.create(
        sender=wallet,
        receiver=platform_wallet,
        amount=SUBSCRIPTION_PRICE,
        transaction_type="autopost_subscription",
        reference=reference,
    )

    entitlement = AutoPostEntitlement.objects.create(
        account=account,
        source=AutoPostEntitlement.SOURCE_PAID,
        reference=reference,
        starts_at=now,
        expires_at=now + SUBSCRIPTION_DURATION,
        payment_transaction=payment,
    )

    return entitlement, True
