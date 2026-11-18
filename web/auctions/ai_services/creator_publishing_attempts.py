"""
Durable ownership for legacy AI creator publishing attempts.

This service does not schedule retries, delete media, or modify
promotional publishing.
"""

import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from auctions.models import (
    CreatorPublishingAttempt,
    ScheduledPublication,
)



def create_attempt_for_locked_publication(
    publication,
    lease_minutes=30,
):
    """
    Create an attempt while the caller holds the publication
    row lock inside an active database transaction.

    Caller is responsible for committing or rolling back
    the publication claim and this attempt together.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError(
            "Publishing attempt requires an atomic transaction."
        )

    if lease_minutes <= 0:
        raise ValueError("Publishing lease must be positive.")

    if publication.status != ScheduledPublication.STATUS_PUBLISHING:
        return None

    if publication.media_asset_id is not None:
        return None

    if publication.feed_post_id is not None:
        return None

    if CreatorPublishingAttempt.objects.filter(
        publication=publication,
        status=CreatorPublishingAttempt.STATUS_ACTIVE,
    ).exists():
        return None

    now = timezone.now()
    token = uuid.uuid4()

    attempt = CreatorPublishingAttempt.objects.create(
        publication=publication,
        token=token,
        status=CreatorPublishingAttempt.STATUS_ACTIVE,
        claimed_at=now,
        lease_expires_at=now + timedelta(minutes=lease_minutes),
        media_namespace=(
            f"feed/media/creator-publishing/{token}/"
        ),
    )

    return attempt.pk, token

def claim_publishing_attempt(publication_id, lease_minutes=30):
    """
    Claim an already-PUBLISHING legacy creator publication.

    Returns (attempt_id, token), or None if ineligible.
    """
    if lease_minutes <= 0:
        raise ValueError("Publishing lease must be positive.")

    now = timezone.now()

    with transaction.atomic():
        publication = (
            ScheduledPublication.objects
            .select_for_update()
            .get(pk=publication_id)
        )

        if publication.status != ScheduledPublication.STATUS_PUBLISHING:
            return None

        if publication.media_asset_id is not None:
            return None

        if publication.feed_post_id is not None:
            return None

        if CreatorPublishingAttempt.objects.filter(
            publication=publication,
            status=CreatorPublishingAttempt.STATUS_ACTIVE,
        ).exists():
            return None

        token = uuid.uuid4()

        attempt = CreatorPublishingAttempt.objects.create(
            publication=publication,
            token=token,
            status=CreatorPublishingAttempt.STATUS_ACTIVE,
            claimed_at=now,
            lease_expires_at=now + timedelta(minutes=lease_minutes),
            media_namespace=(
                f"feed/media/creator-publishing/{token}/"
            ),
        )

        return attempt.pk, token


def verify_publishing_attempt(attempt_id, token):
    """
    Return True only for a live, active publishing attempt.
    """
    now = timezone.now()

    return CreatorPublishingAttempt.objects.filter(
        pk=attempt_id,
        token=token,
        status=CreatorPublishingAttempt.STATUS_ACTIVE,
        lease_expires_at__gt=now,
        publication__status=ScheduledPublication.STATUS_PUBLISHING,
        publication__media_asset__isnull=True,
        publication__feed_post__isnull=True,
    ).exists()



def validate_locked_publishing_attempt(
    publication,
    attempt_id,
    token,
):
    """
    Validate ownership while the caller holds the publication
    row lock inside an atomic transaction.

    Lock order: publication first, publishing attempt second.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError(
            "Publishing ownership validation requires a transaction."
        )

    attempt = (
        CreatorPublishingAttempt.objects
        .select_for_update()
        .filter(
            pk=attempt_id,
            publication_id=publication.pk,
        )
        .first()
    )

    if (
        attempt is None
        or attempt.token != token
        or attempt.status != CreatorPublishingAttempt.STATUS_ACTIVE
        or attempt.lease_expires_at <= timezone.now()
    ):
        raise RuntimeError(
            "Publishing attempt ownership mismatch or expired."
        )

    if (
        publication.status != ScheduledPublication.STATUS_PUBLISHING
        or publication.media_asset_id is not None
        or publication.feed_post_id is not None
    ):
        raise RuntimeError(
            "Publication is not eligible for creator publishing."
        )

    return attempt

def complete_publishing_attempt(attempt_id, token):
    """
    Complete an active attempt for an already-published creator post.

    This standalone function is not yet a transaction-level
    publishing fence. The publisher must eventually finalize the
    publication and attempt within the same transaction.
    """
    with transaction.atomic():
        publication_id = (
            CreatorPublishingAttempt.objects
            .filter(pk=attempt_id)
            .values_list("publication_id", flat=True)
            .get()
        )

        # Consistent lock order: publication before attempt.
        publication = (
            ScheduledPublication.objects
            .select_for_update()
            .get(pk=publication_id)
        )

        attempt = (
            CreatorPublishingAttempt.objects
            .select_for_update()
            .get(pk=attempt_id)
        )

        if attempt.publication_id != publication.pk:
            raise RuntimeError(
                "Publishing attempt publication changed."
            )

        if (
            attempt.token != token
            or attempt.status != CreatorPublishingAttempt.STATUS_ACTIVE
            or attempt.lease_expires_at <= timezone.now()
        ):
            raise RuntimeError(
                "Publishing attempt ownership mismatch or expired."
            )

        if publication.media_asset_id is not None:
            raise RuntimeError(
                "Promotional publication cannot use creator attempt."
            )

        if (
            publication.status != ScheduledPublication.STATUS_PUBLISHED
            or publication.feed_post_id is None
            or publication.published_at is None
        ):
            raise RuntimeError(
                "Cannot complete an unpublished creator attempt."
            )

        attempt.status = CreatorPublishingAttempt.STATUS_COMPLETED
        attempt.completed_at = timezone.now()
        attempt.save(
            update_fields=[
                "status",
                "completed_at",
                "updated_at",
            ]
        )

        return attempt
