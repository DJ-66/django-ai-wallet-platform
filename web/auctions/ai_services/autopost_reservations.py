"""Atomic, idempotent AutoPost reservations. No publishing occurs here."""

from datetime import timedelta
from hashlib import sha256

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auctions.ai_services.autopost_composer import (
    compose_autopost_suffix,
)
from auctions.ai_services.autopost_links import (
    resolve_campaign_destination,
)
from auctions.models import (
    AutoPostConfiguration,
    AutoPostPublication,
    PlatformMediaAsset,
)


@transaction.atomic
def reserve_autopost(*, account_id, request_key, scheduled_for):
    if not isinstance(request_key, str) or not request_key.strip():
        raise ValidationError("Reservation request key is required.")

    request_key = request_key.strip()
    publication_key = "autopost:" + sha256(
        f"{account_id}:{request_key}".encode("utf-8")
    ).hexdigest()

    if timezone.is_naive(scheduled_for):
        raise ValidationError("Scheduled time must be timezone-aware.")

    config = (
        AutoPostConfiguration.objects
        .select_for_update()
        .get(account_id=account_id)
    )

    existing = AutoPostPublication.objects.filter(
        publication_key=publication_key,
        configuration=config,
    ).first()

    if existing is not None:
        return existing

    if not config.enabled:
        raise ValidationError("AutoPost is disabled for this account.")

    from auctions.ai_services.autopost_entitlements import (
        has_active_autopost_entitlement,
    )

    if not has_active_autopost_entitlement(account_id=account_id):
        raise ValidationError(
            "Active AutoPost entitlement required."
        )

    config.full_clean()

    if scheduled_for < timezone.now() + timedelta(hours=24):
        raise ValidationError(
            "AutoPost requires at least 24 hours of scheduling lead time."
        )

    interval = timedelta(hours=config.interval_hours)

    earlier = (
        AutoPostPublication.objects
        .filter(
            configuration=config,
            scheduled_for__lte=scheduled_for,
        )
        .order_by("-scheduled_for", "-pk")
        .first()
    )

    later = (
        AutoPostPublication.objects
        .filter(
            configuration=config,
            scheduled_for__gt=scheduled_for,
        )
        .order_by("scheduled_for", "pk")
        .first()
    )

    if (
        (earlier and scheduled_for - earlier.scheduled_for < interval)
        or (later and later.scheduled_for - scheduled_for < interval)
    ):
        raise ValidationError(
            "AutoPost schedule violates the account posting interval."
        )

    assets = list(
        PlatformMediaAsset.objects
        .select_for_update()
        .filter(
            account_id=account_id,
            is_active=True,
        )
        .order_by("display_order", "pk")
    )

    if not assets:
        raise ValidationError("No active AutoPost images available.")

    index = config.next_media_index % len(assets)
    asset = assets[index]

    if not asset.image.storage.exists(asset.image.name):
        raise ValidationError("Selected AutoPost image is missing.")

    tags = config.approved_hashtags
    if (
        not isinstance(tags, list)
        or len(tags) != 6
        or len(set(tags)) != 6
    ):
        raise ValidationError(
            "Six approved hashtags are required for reservation."
        )

    sequence = config.next_sequence

    suffix = compose_autopost_suffix(
        publication_key=publication_key,
        post_number=sequence,
        cta_every=config.cta_every,
        personality=config.personality,
        enabled_campaigns=tuple(config.enabled_campaigns),
        custom_title=config.custom_cta_title,
    )

    destination_url = ""
    if suffix.kind == "cta":
        if suffix.campaign == "custom":
            destination = resolve_campaign_destination(
                campaign="custom",
                custom_url=config.custom_cta_url,
            )
        else:
            destination = resolve_campaign_destination(
                campaign=suffix.campaign,
            )
        destination_url = destination.url

    reservation = AutoPostPublication.objects.create(
        configuration=config,
        publication_key=publication_key,
        sequence_number=sequence,
        media_asset=asset,
        scheduled_for=scheduled_for,
        personality=suffix.personality,
        campaign=suffix.campaign or "",
        variant_index=suffix.variant_index,
        destination_url=destination_url,
        suffix_translations=dict(suffix.translations),
        reserved_hashtags=list(tags),
    )

    config.next_sequence = sequence + 1
    config.next_media_index += 1
    config.save(update_fields=[
        "next_sequence",
        "next_media_index",
    ])

    return reservation
