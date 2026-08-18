from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    FounderAccount,
    FounderListing,
)


TIENDA_FIXED_TARGET = 10
TIENDA_BLIND_TARGET = 10
TIENDA_SWAMP_TARGET = 10


def _active_tienda_count(lane):
    return FounderListing.objects.filter(
        listing_source=FounderListing.SOURCE_TIENDA,
        tienda_lane=lane,
        status=FounderListing.STATUS_ACTIVE,
    ).count()


def _eligible_tienda_assets():
    return (
        FounderAccount.objects
        .filter(
            status__in=[
                FounderAccount.STATUS_AVAILABLE,
                FounderAccount.STATUS_TREASURY,
            ],
        )
        .exclude(
            listings__status=FounderListing.STATUS_ACTIVE,
        )
        .order_by(
            "handle_length",
            "handle",
        )
    )


@transaction.atomic
def replenish_founder_tienda(
    *,
    fixed_handles=None,
    blind_handles=None,
    swamp_handles=None,
):
    """
    Refill the FANZ Founder Tienda toward:

    10 fixed-price listings
    10 blind-sale listings
    10 Swamp Land listings

    Optional handle lists allow FANZ to curate specific properties
    into specific lanes. Any remaining deficit is filled from other
    eligible Treasury inventory.
    """

    fixed_handles = [
        str(handle).lower()
        for handle in (fixed_handles or [])
    ]

    blind_handles = [
        str(handle).lower()
        for handle in (blind_handles or [])
    ]

    swamp_handles = [
        str(handle).lower()
        for handle in (swamp_handles or [])
    ]

    requested_handles = (
        fixed_handles
        + blind_handles
        + swamp_handles
    )

    if len(requested_handles) != len(set(requested_handles)):
        raise ValidationError(
            "The same Founder property cannot be curated into "
            "multiple Tienda lanes."
        )

    fixed_missing = max(
        0,
        TIENDA_FIXED_TARGET
        - _active_tienda_count(FounderListing.TIENDA_FIXED),
    )

    blind_missing = max(
        0,
        TIENDA_BLIND_TARGET
        - _active_tienda_count(FounderListing.TIENDA_BLIND),
    )

    swamp_missing = max(
        0,
        TIENDA_SWAMP_TARGET
        - _active_tienda_count(FounderListing.TIENDA_SWAMP),
    )

    if (
        fixed_missing == 0
        and blind_missing == 0
        and swamp_missing == 0
    ):
        return {
            "fixed_created": 0,
            "blind_created": 0,
            "swamp_created": 0,
        }

    eligible = (
        _eligible_tienda_assets()
        .select_for_update()
    )

    eligible_by_handle = {
        asset.handle: asset
        for asset in eligible
    }

    used_ids = set()

    def choose_assets(handles, count):
        chosen = []

        for handle in handles:
            if len(chosen) >= count:
                break

            asset = eligible_by_handle.get(handle)

            if asset is None:
                raise ValidationError(
                    f"Curated Founder property @{handle} "
                    f"is not eligible for Tienda inventory."
                )

            if asset.pk in used_ids:
                raise ValidationError(
                    f"Founder property @{handle} "
                    f"was selected more than once."
                )

            chosen.append(asset)
            used_ids.add(asset.pk)

        if len(chosen) < count:
            for asset in eligible_by_handle.values():
                if len(chosen) >= count:
                    break

                if asset.pk in used_ids:
                    continue

                chosen.append(asset)
                used_ids.add(asset.pk)

        if len(chosen) < count:
            raise ValidationError(
                "Not enough eligible Founder inventory "
                "to replenish Tienda."
            )

        return chosen

    fixed_assets = choose_assets(
        fixed_handles,
        fixed_missing,
    )

    blind_assets = choose_assets(
        blind_handles,
        blind_missing,
    )

    swamp_assets = choose_assets(
        swamp_handles,
        swamp_missing,
    )

    created = {
        "fixed_created": 0,
        "blind_created": 0,
        "swamp_created": 0,
    }

    for asset in fixed_assets:
        FounderListing.objects.create(
            founder_account=asset,
            seller_root=asset.owner_root,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_FIXED,
            sale_type=FounderListing.SALE_FIXED,
            fixed_price_credits=max(
                asset.floor_price_credits,
                1000,
            ),
            status=FounderListing.STATUS_ACTIVE,
        )

        asset.status = FounderAccount.STATUS_LISTED
        asset.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        created["fixed_created"] += 1

    for asset in blind_assets:
        FounderListing.objects.create(
            founder_account=asset,
            seller_root=asset.owner_root,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_BLIND,
            sale_type=FounderListing.SALE_BLIND,
            minimum_bid_credits=max(
                asset.floor_price_credits,
                500,
            ),
            ends_at=(
                timezone.now()
                + timedelta(days=3)
            ),
            status=FounderListing.STATUS_ACTIVE,
        )

        asset.status = FounderAccount.STATUS_LISTED
        asset.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        created["blind_created"] += 1

    for asset in swamp_assets:
        FounderListing.objects.create(
            founder_account=asset,
            seller_root=asset.owner_root,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_SWAMP,
            sale_type=FounderListing.SALE_FIXED,
            fixed_price_credits=200,
            status=FounderListing.STATUS_ACTIVE,
        )

        asset.status = FounderAccount.STATUS_LISTED
        asset.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        created["swamp_created"] += 1

    return created
