"""Read-only access checks for FANZ AutoPost Pro."""

from django.utils import timezone

from auctions.models import AutoPostEntitlement


def has_active_autopost_entitlement(*, account_id, at=None):
    """Check pilot access; paid access awaits verified billing."""
    now = at if at is not None else timezone.now()

    return AutoPostEntitlement.objects.filter(
        account_id=account_id,
        source=AutoPostEntitlement.SOURCE_PILOT,
        payment_transaction__isnull=True,
        revoked_at__isnull=True,
        starts_at__lte=now,
        expires_at__gt=now,
    ).exists()
