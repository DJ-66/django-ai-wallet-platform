"""Capture-dependent SunsetCam promotional scheduling."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.utils import timezone

from auctions.models import (
    ScheduledPublication,
    SunsetCamCapture,
    UserProfile,
)
from auctions.promotional_scheduling import (
    promotional_publication_key,
    schedule_promotional_publication,
)


PREPARATION_WINDOW = timedelta(minutes=15)

PROMOTIONAL_SLOTS = {
    "noon": SunsetCamCapture.CAPTURE_MIDDAY,
    "sunset": SunsetCamCapture.CAPTURE_SUNSET_4,
}


def promotional_slot_time(
    *,
    local_date,
    slot,
    timezone_name="America/Asuncion",
    sunset=None,
):
    """Calculate the requested promotional publication time."""

    if slot not in PROMOTIONAL_SLOTS:
        raise ValidationError(
            "Unknown SunsetCam promotional slot."
        )

    tz = ZoneInfo(timezone_name)

    if slot == "noon":
        return datetime.combine(
            local_date,
            time(hour=12, minute=30),
            tzinfo=tz,
        )

    if sunset is None or timezone.is_naive(sunset):
        raise ValidationError(
            "An aware sunset datetime is required."
        )

    if sunset.astimezone(tz).date() != local_date:
        raise ValidationError(
            "Sunset does not match the requested local date."
        )

    return sunset.astimezone(tz) + timedelta(minutes=30)


def schedule_sunsetcam_promotion(
    *,
    account,
    local_date,
    slot,
    referral_url,
    now=None,
    sunset=None,
    timezone_name="America/Asuncion",
):
    """
    Queue one promotion after a successful camera capture.

    Returns (publication, created, reason).

    No publication is created outside the preparation window.
    """

    if slot not in PROMOTIONAL_SLOTS:
        raise ValidationError(
            "Unknown SunsetCam promotional slot."
        )

    if (
        not account.pk
        or account.username.lower() != "sunsetcam"
    ):
        raise ValidationError(
            "Only a saved SunsetCam account is supported."
        )

    if not UserProfile.objects.filter(
        user=account,
        is_platform_account=True,
    ).exists():
        raise ValidationError(
            "SunsetCam platform authorization is required."
        )

    target = promotional_slot_time(
        local_date=local_date,
        slot=slot,
        timezone_name=timezone_name,
        sunset=sunset,
    )

    now = now or timezone.now()

    if timezone.is_naive(now):
        raise ValidationError(
            "An aware current datetime is required."
        )

    capture_exists = SunsetCamCapture.objects.filter(
        local_date=local_date,
        capture_type=PROMOTIONAL_SLOTS[slot],
        post__user=account,
    ).exists()

    if not capture_exists:
        return None, False, "capture_missing"

    publication_key = promotional_publication_key(
        account.pk,
        target,
    )

    existing = ScheduledPublication.objects.filter(
        publication_key=publication_key,
    ).first()

    if existing is not None:
        if (
            existing.creator_id != account.pk
            or existing.scheduled_for != target
            or existing.referral_url != referral_url
        ):
            raise ValidationError(
                "Existing publication conflicts "
                "with requested schedule."
            )

        return existing, False, "existing"

    if now < target - PREPARATION_WINDOW:
        return None, False, "too_early"

    if now >= target:
        return None, False, "expired"

    publication, created = schedule_promotional_publication(
        account=account,
        scheduled_for=target,
        referral_url=referral_url,
    )

    return (
        publication,
        created,
        "scheduled" if created else "existing",
    )
