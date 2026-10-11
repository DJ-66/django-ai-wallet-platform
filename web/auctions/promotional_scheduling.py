"""Explicit, concurrency-safe FANZ promotional scheduling."""

from datetime import timezone as dt_timezone
from hashlib import sha256

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auctions.models import (
    ScheduledPublication,
    UserProfile,
)
from auctions.promotional_overlays import (
    _validate_referral_url,
)
from auctions.promotional_rotation import (
    select_promotional_rotation,
)


def promotional_publication_key(account_id, scheduled_for):
    """Return the deterministic key for an account and UTC slot."""

    if timezone.is_naive(scheduled_for):
        raise ValidationError(
            "An aware publication datetime is required."
        )

    utc_time = scheduled_for.astimezone(dt_timezone.utc)
    slot = utc_time.isoformat(timespec="microseconds")

    digest = sha256(
        f"{account_id}:{slot}".encode()
    ).hexdigest()[:24]

    return f"promo-{account_id}-{digest}"


def schedule_promotional_publication(
    *,
    account,
    scheduled_for,
    referral_url,
):
    """
    Queue one promotional publication.

    No feed posts are created.
    No worker is invoked.
    """

    if not account.pk:
        raise ValidationError("Account must be saved.")

    if (
        scheduled_for is None
        or timezone.is_naive(scheduled_for)
    ):
        raise ValidationError(
            "An aware publication datetime is required."
        )

    if scheduled_for <= timezone.now():
        raise ValidationError(
            "Publication must be scheduled in the future."
        )

    try:
        _validate_referral_url(referral_url)
    except ValueError as exc:
        raise ValidationError(
            "Invalid FANZ referral destination."
        ) from exc

    publication_key = promotional_publication_key(
        account.pk,
        scheduled_for,
    )

    with transaction.atomic():
        # Serialize scheduling for this account.
        profile = (
            UserProfile.objects
            .select_for_update()
            .get(user=account)
        )

        if not profile.is_platform_account:
            raise ValidationError(
                "Promotional scheduling requires "
                "a platform-owned account."
            )

        existing = ScheduledPublication.objects.filter(
            publication_key=publication_key,
        ).first()

        if existing is not None:
            if (
                existing.creator_id != account.pk
                or existing.scheduled_for != scheduled_for
                or existing.referral_url != referral_url
            ):
                raise ValidationError(
                    "Existing publication conflicts "
                    "with requested schedule."
                )

            return existing, False

        selection = select_promotional_rotation(account)

        publication = ScheduledPublication.objects.create(
            publication_key=publication_key,
            creator=account,
            source_path="",
            media_asset_id=selection.media_asset_id,
            campaign_key=selection.campaign_key,
            referral_url=referral_url,
            title="",
            content="",
            scheduled_for=scheduled_for,
            status=ScheduledPublication.STATUS_QUEUED,
        )

        return publication, True
