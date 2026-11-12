"""Reservation identity for FANZ-owned AI publications."""

from django.db import models

from auctions.models import ScheduledPublication


PREPARING_MARKER = "ai_preparing"


def is_ai_preparation_reservation(publication):
    """Recognize only FANZ AI scheduling reservations."""
    return bool(
        publication
        and publication.publication_key.startswith("ai:")
        and publication.media_asset_id is None
        and publication.status == ScheduledPublication.STATUS_DRAFT
        and publication.campaign_key == PREPARING_MARKER
    )


def creator_has_active_ai_publication(creator):
    """Check queued, publishing, or non-superseded AI drafts."""
    ai_posts = ScheduledPublication.objects.filter(
        creator=creator,
        publication_key__startswith="ai:",
    )

    if ai_posts.filter(
        status__in=[
            ScheduledPublication.STATUS_QUEUED,
            ScheduledPublication.STATUS_PUBLISHING,
        ],
    ).exists():
        return True

    drafts = ai_posts.filter(
        status=ScheduledPublication.STATUS_DRAFT,
        campaign_key=PREPARING_MARKER,
    )

    for draft in drafts:
        newer_published = ai_posts.filter(
            status=ScheduledPublication.STATUS_PUBLISHED,
        ).filter(
            models.Q(created_at__gt=draft.created_at)
            | models.Q(
                created_at=draft.created_at,
                pk__gt=draft.pk,
            )
        ).exists()

        if not newer_published:
            return True

    return False


def reserve_ai_publication(
    *,
    creator,
    publication_key,
    source_path,
    scheduled_for,
    title,
    content,
):
    """Atomically reserve one AI publication per creator."""

    from django.db import transaction
    from django.contrib.auth import get_user_model

    if not publication_key.startswith("ai:"):
        raise ValueError("Invalid AI publication key")

    if not source_path or not content:
        raise ValueError("Reservation requires source and content")

    with transaction.atomic():
        locked_creator = (
            get_user_model().objects
            .select_for_update()
            .get(pk=creator.pk)
        )

        if creator_has_active_ai_publication(locked_creator):
            return None

        if ScheduledPublication.objects.filter(
            publication_key=publication_key
        ).exists():
            return None

        return ScheduledPublication.objects.create(
            publication_key=publication_key,
            creator=locked_creator,
            source_path=source_path,
            scheduled_for=scheduled_for,
            title=title,
            content=content,
            campaign_key=PREPARING_MARKER,
            status=ScheduledPublication.STATUS_DRAFT,
        )


def finalize_ai_publication_reservation(
    *,
    reservation_id,
    content,
    marker,
):
    """Reject finalization without lease ownership."""
    raise RuntimeError(
        "Tokenless AI reservation finalization is disabled"
    )




def claim_ai_reservation(*, reservation_id, lease_minutes=30):
    """Claim an unowned or expired AI preparation draft."""
    from datetime import timedelta
    from uuid import uuid4

    from django.db import transaction
    from django.utils import timezone

    from auctions.models import LegacyAIPublicationLease

    if lease_minutes <= 0:
        raise ValueError("Lease duration must be positive")

    with transaction.atomic():
        from django.contrib.auth import get_user_model

        creator_id = (
            ScheduledPublication.objects
            .values_list("creator_id", flat=True)
            .get(pk=reservation_id)
        )

        # Match reservation and finalization lock ordering.
        get_user_model().objects.select_for_update().get(
            pk=creator_id,
        )

        publication = (
            ScheduledPublication.objects
            .select_for_update()
            .get(pk=reservation_id)
        )

        if publication.creator_id != creator_id:
            return None

        if not is_ai_preparation_reservation(publication):
            return None

        # Do not lease a stale draft when another AI post
        # is already queued or publishing for this creator.
        competing = ScheduledPublication.objects.filter(
            creator_id=creator_id,
            publication_key__startswith="ai:",
            status__in=[
                ScheduledPublication.STATUS_QUEUED,
                ScheduledPublication.STATUS_PUBLISHING,
            ],
        ).exclude(pk=publication.pk).exists()

        if competing:
            return None

        # A newer published AI post supersedes this old draft.
        # Older published history must not prevent recovery.
        superseded = ScheduledPublication.objects.filter(
            creator_id=creator_id,
            publication_key__startswith="ai:",
            status=ScheduledPublication.STATUS_PUBLISHED,
        ).filter(
            models.Q(created_at__gt=publication.created_at)
            | models.Q(
                created_at=publication.created_at,
                pk__gt=publication.pk,
            )
        ).exists()

        if superseded:
            return None

        lease, _ = (
            LegacyAIPublicationLease.objects
            .select_for_update()
            .get_or_create(publication=publication)
        )

        now = timezone.now()

        if (
            lease.next_retry_at is not None
            and lease.next_retry_at > now
        ):
            return None

        if (
            lease.claim_token is not None
            and (
                lease.lease_expires_at is None
                or lease.lease_expires_at > now
            )
        ):
            return None

        token = uuid4()

        lease.claim_token = token
        lease.claimed_at = now
        lease.lease_expires_at = now + timedelta(
            minutes=lease_minutes
        )
        lease.next_retry_at = None

        lease.save(
            update_fields=[
                "claim_token",
                "claimed_at",
                "lease_expires_at",
                "next_retry_at",
                "updated_at",
            ]
        )

        return publication.pk, token


def verify_ai_reservation_claim(reservation_id, token):
    """Verify that a worker still owns an unexpired draft."""
    from django.utils import timezone

    from auctions.models import LegacyAIPublicationLease

    return LegacyAIPublicationLease.objects.filter(
        publication_id=reservation_id,
        publication__status=ScheduledPublication.STATUS_DRAFT,
        publication__campaign_key=PREPARING_MARKER,
        publication__publication_key__startswith="ai:",
        publication__media_asset__isnull=True,
        claim_token=token,
        lease_expires_at__gt=timezone.now(),
    ).exists()


def finalize_claimed_ai_reservation(
    *,
    reservation_id,
    token,
    content,
    marker,
):
    """Queue a prepared AI post only for its live lease owner."""
    from django.db import transaction
    from django.utils import timezone

    from auctions.models import LegacyAIPublicationLease
    from auctions.ai_services.legacy_prepared_validation import (
        MARKERS,
        validate_prepared_publication,
    )
    from auctions.ai_services.legacy_suffix_adapter import (
        publication_sequence,
    )

    if marker not in MARKERS:
        raise ValueError("Invalid preparation marker")

    if not content or len(content) > 2000:
        raise ValueError("Invalid prepared caption")

    with transaction.atomic():
        from django.contrib.auth import get_user_model

        # Read the creator ID before acquiring row locks.
        creator_id = (
            ScheduledPublication.objects
            .values_list("creator_id", flat=True)
            .get(pk=reservation_id)
        )

        # Consistent lock order: creator -> publication -> lease.
        get_user_model().objects.select_for_update().get(
            pk=creator_id,
        )

        publication = (
            ScheduledPublication.objects
            .select_for_update()
            .select_related("creator")
            .get(pk=reservation_id)
        )

        # Recheck after locking: the creator relationship
        # must not have changed between the two reads.
        if publication.creator_id != creator_id:
            return False

        if not is_ai_preparation_reservation(publication):
            return False

        # Never finalize an old draft while another AI post
        # for this creator is already queued or publishing.
        competing = ScheduledPublication.objects.filter(
            creator_id=publication.creator_id,
            publication_key__startswith="ai:",
            status__in=[
                ScheduledPublication.STATUS_QUEUED,
                ScheduledPublication.STATUS_PUBLISHING,
            ],
        ).exclude(pk=publication.pk).exists()

        if competing:
            return False

        # A newer published AI post supersedes this draft,
        # even if the draft was claimed before that post went live.
        superseded = ScheduledPublication.objects.filter(
            creator_id=publication.creator_id,
            publication_key__startswith="ai:",
            status=ScheduledPublication.STATUS_PUBLISHED,
        ).filter(
            models.Q(created_at__gt=publication.created_at)
            | models.Q(
                created_at=publication.created_at,
                pk__gt=publication.pk,
            )
        ).exists()

        if superseded:
            return False

        lease = (
            LegacyAIPublicationLease.objects
            .select_for_update()
            .filter(
                publication=publication,
                claim_token=token,
                lease_expires_at__gt=timezone.now(),
            )
            .first()
        )

        if lease is None:
            return False

        sequence = publication_sequence(publication)

        validate_prepared_publication(
            username=publication.creator.username,
            publication_key=publication.publication_key,
            sequence=sequence,
            marker=marker,
            content=content,
        )

        publication.content = content
        publication.campaign_key = marker
        publication.status = ScheduledPublication.STATUS_QUEUED

        publication.save(
            update_fields=[
                "content",
                "campaign_key",
                "status",
                "updated_at",
            ]
        )

        lease.claim_token = None
        lease.claimed_at = None
        lease.lease_expires_at = None
        lease.next_retry_at = None
        lease.last_error = ""

        lease.save(
            update_fields=[
                "claim_token",
                "claimed_at",
                "lease_expires_at",
                "next_retry_at",
                "last_error",
                "updated_at",
            ]
        )

        return True


def fail_ai_reservation_claim(
    *,
    reservation_id,
    token,
    error,
):
    """Record preparation failure only for the current lease owner."""
    from datetime import timedelta

    from django.db import transaction
    from django.utils import timezone

    from auctions.models import LegacyAIPublicationLease

    with transaction.atomic():
        publication = (
            ScheduledPublication.objects
            .select_for_update()
            .get(pk=reservation_id)
        )

        if not is_ai_preparation_reservation(publication):
            return False

        lease = (
            LegacyAIPublicationLease.objects
            .select_for_update()
            .filter(
                publication=publication,
                claim_token=token,
                lease_expires_at__gt=timezone.now(),
            )
            .first()
        )

        if lease is None:
            return False

        lease.attempt_count += 1

        delay_minutes = min(
            30 * (2 ** min(lease.attempt_count - 1, 6)),
            1440,
        )

        lease.last_error = str(error)[:2000]
        lease.next_retry_at = (
            timezone.now() + timedelta(minutes=delay_minutes)
        )

        lease.claim_token = None
        lease.claimed_at = None
        lease.lease_expires_at = None

        lease.save(
            update_fields=[
                "attempt_count",
                "last_error",
                "next_retry_at",
                "claim_token",
                "claimed_at",
                "lease_expires_at",
                "updated_at",
            ]
        )

        return True


def claim_existing_ai_preparation(*, creator, lease_minutes=30):
    """Reclaim a creator's existing AI draft when eligible."""
    from auctions.models import ScheduledPublication

    reservation = (
        ScheduledPublication.objects
        .filter(
            creator=creator,
            publication_key__startswith="ai:",
            status=ScheduledPublication.STATUS_DRAFT,
            campaign_key=PREPARING_MARKER,
            media_asset__isnull=True,
        )
        .order_by("scheduled_for", "pk")
        .first()
    )

    if reservation is None:
        return None

    return claim_ai_reservation(
        reservation_id=reservation.pk,
        lease_minutes=lease_minutes,
    )
