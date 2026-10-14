"""Verified access checks for FANZ AutoPost Pro."""

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from auctions.models import AutoPostEntitlement
from auctions.utils import SYSTEM_WALLET_USERNAME


def has_active_autopost_entitlement(*, account_id, at=None):
    """Accept authorized pilots or verified paid subscriptions."""
    now = at if at is not None else timezone.now()

    valid_pilot = Q(
        source=AutoPostEntitlement.SOURCE_PILOT,
        payment_transaction__isnull=True,
    )

    valid_paid = Q(
        source=AutoPostEntitlement.SOURCE_PAID,
        payment_transaction__isnull=False,
        payment_transaction__transaction_type="autopost_subscription",
        payment_transaction__amount=Decimal("150.00"),
        payment_transaction__sender__user_id=account_id,
        payment_transaction__receiver__user__username=SYSTEM_WALLET_USERNAME,
    )

    return AutoPostEntitlement.objects.filter(
        valid_pilot | valid_paid,
        account_id=account_id,
        revoked_at__isnull=True,
        starts_at__lte=now,
        expires_at__gt=now,
    ).exists()
