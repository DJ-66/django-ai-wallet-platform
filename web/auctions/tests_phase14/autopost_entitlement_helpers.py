"""Test-only AutoPost pilot entitlement fixtures."""

from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from auctions.models import AutoPostEntitlement


def grant_autopost_pilot(account):
    now = timezone.now()

    return AutoPostEntitlement.objects.create(
        account=account,
        source=AutoPostEntitlement.SOURCE_PILOT,
        reference=f"test-pilot:{uuid4()}",
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=7),
    )
