"""Short-transaction processing claims for AutoPost."""

from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from auctions.models import AutoPostPublication


def claim_autopost(*, lease_minutes=30):
    """Claim one eligible reservation without running AI inference."""
    if lease_minutes <= 0:
        raise ValueError("Lease duration must be positive.")

    now = timezone.now()

    with transaction.atomic():
        publication = (
            AutoPostPublication.objects
            .select_for_update(skip_locked=True)
            .filter(
                Q(status=AutoPostPublication.STATUS_RESERVED)
                | Q(
                    status=AutoPostPublication.STATUS_FAILED,
                    next_retry_at__lte=now,
                )
                | Q(
                    status=AutoPostPublication.STATUS_PROCESSING,
                    lease_expires_at__lte=now,
                )
            )
            .filter(
                configuration__enabled=True,
                configuration__account__is_active=True,
                scheduled_for__lte=now + timedelta(hours=24),
            )
            .order_by("scheduled_for", "pk")
            .first()
        )

        if publication is None:
            return None

        token = uuid4()

        publication.status = AutoPostPublication.STATUS_PROCESSING
        publication.claim_token = token
        publication.claimed_at = now
        publication.lease_expires_at = now + timedelta(
            minutes=lease_minutes,
        )
        publication.next_retry_at = None

        publication.save(update_fields=[
            "status",
            "claim_token",
            "claimed_at",
            "lease_expires_at",
            "next_retry_at",
            "updated_at",
        ])

        return publication.pk, token


def verify_autopost_claim(publication_id, token):
    """Return True only for the current, unexpired claim."""
    return AutoPostPublication.objects.filter(
        pk=publication_id,
        status=AutoPostPublication.STATUS_PROCESSING,
        claim_token=token,
        lease_expires_at__gt=timezone.now(),
    ).exists()


def complete_autopost(publication_id, token, translations, hashtags):
    """Persist validated captions only for the live claim owner."""
    from auctions.management.commands.repair_creator_captions import (
        validate_recovery_translations,
    )

    with transaction.atomic():
        publication = (
            AutoPostPublication.objects.select_for_update()
            .filter(
                pk=publication_id,
                status=AutoPostPublication.STATUS_PROCESSING,
                claim_token=token,
                lease_expires_at__gt=timezone.now(),
            )
            .first()
        )

        if publication is None:
            return False

        validate_recovery_translations(translations, hashtags)

        publication.translations = translations
        publication.status = AutoPostPublication.STATUS_READY
        publication.claim_token = None
        publication.claimed_at = None
        publication.lease_expires_at = None
        publication.next_retry_at = None
        publication.last_error = ""

        publication.save(update_fields=[
            "translations", "status", "claim_token",
            "claimed_at", "lease_expires_at",
            "next_retry_at", "last_error", "updated_at",
        ])

        return True


def fail_autopost(publication_id, token, error):
    """Record failure without allowing stale workers to change state."""
    with transaction.atomic():
        publication = (
            AutoPostPublication.objects.select_for_update()
            .filter(
                pk=publication_id,
                status=AutoPostPublication.STATUS_PROCESSING,
                claim_token=token,
                lease_expires_at__gt=timezone.now(),
            )
            .first()
        )

        if publication is None:
            return False

        publication.attempt_count += 1
        delay = min(
            30 * (2 ** min(publication.attempt_count - 1, 6)),
            1440,
        )

        publication.status = AutoPostPublication.STATUS_FAILED
        publication.last_error = str(error)[:2000]
        publication.next_retry_at = (
            timezone.now() + timedelta(minutes=delay)
        )
        publication.claim_token = None
        publication.claimed_at = None
        publication.lease_expires_at = None

        publication.save(update_fields=[
            "status", "attempt_count", "last_error",
            "next_retry_at", "claim_token",
            "claimed_at", "lease_expires_at", "updated_at",
        ])

        return True
