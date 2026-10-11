"""Deterministic, read-only FANZ promotional rotation selector."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from auctions.models import (
    PlatformMediaAsset,
    ScheduledPublication,
)
from auctions.promotional_campaigns import CAMPAIGNS


@dataclass(frozen=True)
class RotationSelection:
    campaign_key: str
    media_asset_id: int


def select_promotional_rotation(account):
    """
    Choose the next approved campaign and reusable media asset.

    No database writes.
    No publication creation.
    No AI-generated offers.
    """

    if not account.pk:
        raise ValidationError("Account must be saved.")

    campaigns = sorted(
        key
        for key, campaign in CAMPAIGNS.items()
        if not campaign.requires_offer_verification
    )

    if not campaigns:
        raise ValidationError(
            "No approved promotional campaigns."
        )

    assets = list(
        PlatformMediaAsset.objects.filter(
            account=account,
            is_active=True,
        ).order_by("display_order", "pk")
    )

    if not assets:
        raise ValidationError(
            "No active promotional media."
        )

    history = list(
        ScheduledPublication.objects.filter(
            creator=account,
            media_asset__isnull=False,
        ).exclude(
            status=ScheduledPublication.STATUS_FAILED,
        ).order_by("created_at", "pk")
        .values_list("campaign_key", "media_asset_id")
    )

    # Only configured campaigns participate in rotation history.
    history = [
        (campaign, media_id)
        for campaign, media_id in history
        if campaign in campaigns
    ]

    last_campaign = (
        history[-1][0]
        if history
        else None
    )

    if last_campaign in campaigns:
        campaign_index = (
            campaigns.index(last_campaign) + 1
        ) % len(campaigns)
    else:
        campaign_index = 0

    active_ids = [asset.pk for asset in assets]

    last_media_id = (
        history[-1][1]
        if history
        else None
    )

    if last_media_id in active_ids:
        media_index = (
            active_ids.index(last_media_id) + 1
        ) % len(active_ids)
    else:
        media_index = 0

    return RotationSelection(
        campaign_key=campaigns[campaign_index],
        media_asset_id=active_ids[media_index],
    )
