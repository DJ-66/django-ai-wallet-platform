"""Safe replenishment of existing Founder Tienda Blind Offer inventory."""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from .founder_services import is_protected_founder
from .founder_tienda import TIENDA_BLIND_TARGET
from .models import (
    FounderAccount,
    FounderCartItem,
    FounderBid,
    FounderCreditHold,
    FounderListing,
    FounderVendingHold,
)
from .utils import SYSTEM_WALLET_USERNAME


# Stable PostgreSQL advisory-lock namespace for Tienda replenishment.
TIENDA_LOCK_NAMESPACE = 117505
TIENDA_LOCK_KEY = 1

BLIND_DURATION = timedelta(days=3)
BLIND_MINIMUM_CREDITS = 500


def lock_tienda_replenishment():
    """Serialize cooperating Tienda replenishment transactions."""
    if connection.vendor != "postgresql":
        raise RuntimeError(
            "Tienda replenishment requires PostgreSQL."
        )

    if not connection.in_atomic_block:
        raise RuntimeError(
            "Tienda replenishment requires an atomic transaction."
        )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            [TIENDA_LOCK_NAMESPACE, TIENDA_LOCK_KEY],
        )


def _active_blind_listings():
    return FounderListing.objects.filter(
        listing_source=FounderListing.SOURCE_TIENDA,
        tienda_lane=FounderListing.TIENDA_BLIND,
        status=FounderListing.STATUS_ACTIVE,
    )


def _eligible_asset(asset, platform_id, now):
    """Revalidate eligibility while the Founder row is locked."""
    if asset.owner_root_id != platform_id:
        return False

    if asset.current_account_id is not None:
        return False

    if asset.status not in {
        FounderAccount.STATUS_AVAILABLE,
        FounderAccount.STATUS_TREASURY,
    }:
        return False

    if is_protected_founder(asset):
        return False

    if get_user_model().objects.filter(
        username__iexact=asset.handle
    ).exists():
        return False

    if FounderListing.objects.filter(
        founder_account=asset,
        status=FounderListing.STATUS_ACTIVE,
    ).exists():
        return False

    # Completed sales must never be automatically recycled.
    if FounderListing.objects.filter(
        founder_account=asset,
        status=FounderListing.STATUS_SOLD,
    ).exists():
        return False

    # An unresolved bid is a financial obligation even if
    # its historical listing is no longer marked active.
    if FounderBid.objects.filter(
        listing__founder_account=asset,
        status=FounderBid.STATUS_ACTIVE,
    ).exists():
        return False

    # Never recycle a property while any historical bid
    # still has customer credits held against it.
    if FounderCreditHold.objects.filter(
        bid__listing__founder_account=asset,
        status=FounderCreditHold.STATUS_HELD,
    ).exists():
        return False

    if FounderCartItem.objects.filter(
        wanted_handle__iexact=asset.handle,
        status=FounderCartItem.STATUS_QUOTED,
        reservation_expires_at__gt=now,
    ).exists():
        return False

    if FounderVendingHold.objects.filter(
        cart_item__wanted_handle__iexact=asset.handle,
        status=FounderVendingHold.STATUS_HELD,
    ).exists():
        return False

    return True


@transaction.atomic
def replenish_blind_offers():
    """
    Fill vacant Blind Offer slots without provisioning new properties.

    Expiration and settlement remain the responsibility of the
    existing Founder settlement service.

    Unresolved active listings occupy inventory slots until
    safely closed. Never bypass them by changing their status.
    """
    from .management.commands.replenish_founder_tienda import (
        BLIND_HANDLES,
        BLIND_RESERVE_HANDLES,
    )

    lock_tienda_replenishment()

    now = timezone.now()

    active_before = _active_blind_listings().count()
    missing = max(0, TIENDA_BLIND_TARGET - active_before)

    result = {
        "target": TIENDA_BLIND_TARGET,
        "active_before": active_before,
        "active_after": active_before,
        "created": 0,
        "shortage": missing,
        "handles": [],
    }

    if missing == 0:
        return result

    platform = get_user_model().objects.get(
        username=SYSTEM_WALLET_USERNAME
    )

    curated = set(BLIND_HANDLES + BLIND_RESERVE_HANDLES)

    candidate_ids = list(
        FounderAccount.objects.filter(
            handle__in=curated,
            owner_root_id=platform.pk,
            current_account__isnull=True,
            status__in=[
                FounderAccount.STATUS_AVAILABLE,
                FounderAccount.STATUS_TREASURY,
            ],
        )
        .exclude(
            listings__status=FounderListing.STATUS_ACTIVE
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )

    history = dict(
        FounderListing.objects.filter(
            founder_account_id__in=candidate_ids,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_BLIND,
        )
        .values("founder_account_id")
        .annotate(last_offered=Max("created_at"))
        .values_list("founder_account_id", "last_offered")
    )

    fresh = [
        pk for pk in candidate_ids
        if pk not in history
    ]

    previous = [
        pk for pk in candidate_ids
        if pk in history
    ]

    random.shuffle(fresh)
    random.shuffle(previous)

    # Prefer never-offered inventory, then older inventory.
    # The shuffle randomizes ties in historical listing times.
    previous.sort(key=lambda pk: history[pk])

    ranked_ids = fresh + previous

    for asset_id in ranked_ids:
        if result["created"] >= missing:
            break

        asset = (
            FounderAccount.objects
            .select_for_update(skip_locked=True)
            .filter(pk=asset_id)
            .first()
        )

        if asset is None:
            continue

        checked_at = timezone.now()

        if asset.handle not in curated:
            continue

        if not _eligible_asset(
            asset,
            platform.pk,
            checked_at,
        ):
            continue

        FounderListing.objects.create(
            founder_account=asset,
            seller_root_id=platform.pk,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_BLIND,
            sale_type=FounderListing.SALE_BLIND,
            minimum_bid_credits=max(
                asset.floor_price_credits,
                BLIND_MINIMUM_CREDITS,
            ),
            starts_at=checked_at,
            ends_at=checked_at + BLIND_DURATION,
            status=FounderListing.STATUS_ACTIVE,
        )

        asset.status = FounderAccount.STATUS_LISTED
        asset.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        result["created"] += 1
        result["handles"].append(asset.handle)

    result["active_after"] = _active_blind_listings().count()
    result["shortage"] = max(
        0,
        TIENDA_BLIND_TARGET - result["active_after"],
    )

    return result
