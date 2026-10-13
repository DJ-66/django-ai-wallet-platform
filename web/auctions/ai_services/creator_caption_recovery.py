"""
Persistent claims for historical FANZ creator caption recovery.

This module does not generate AI content or update feed posts.
"""

import uuid
from pathlib import Path
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from auctions.models import (
    CreatorCaptionRecoveryState,
    ScheduledPublication,
)
from auctions.management.commands.repair_creator_captions import (
    GENERIC_TITLES,
    GENERIC_CAPTIONS,
)


ELIGIBLE_STATUSES = (
    ScheduledPublication.STATUS_QUEUED,
    ScheduledPublication.STATUS_PUBLISHED,
)


def is_generic_publication(publication):
    caption = publication.content.split("\n\n")[0].strip()

    return (
        publication.title in GENERIC_TITLES
        or caption in GENERIC_CAPTIONS
    )


def claim_next_publication(*, lease_minutes=30, queued_only=False, published_only=False, min_lead_minutes=0):
    """
    Claim one approved generic creator publication.

    Prioritize queued, then published.
    Do not hold publication locks during inference.
    """
    import json

    from django.db.models import Q

    from auctions.management.commands.generate_ai_publications import (
        MANIFEST_PATH,
    )

    if lease_minutes <= 0:
        raise ValueError("Lease duration must be positive.")

    if min_lead_minutes < 0:
        raise ValueError("Minimum lead time cannot be negative.")

    if queued_only and published_only:
        raise ValueError(
            "Cannot request queued-only and published-only together."
        )

    manifest = json.loads(Path(MANIFEST_PATH).read_text())

    approved_accounts = {
        item["account"].casefold()
        for item in manifest["creators"]
    }

    now = timezone.now()

    generic_filter = Q(title__in=GENERIC_TITLES)

    for caption in GENERIC_CAPTIONS:
        generic_filter |= Q(content=caption)
        generic_filter |= Q(
            content__startswith=caption + "\\n\\n"
        )

    if queued_only:
        statuses = (ScheduledPublication.STATUS_QUEUED,)
    elif published_only:
        statuses = (ScheduledPublication.STATUS_PUBLISHED,)
    else:
        statuses = ELIGIBLE_STATUSES

    for publication_status in statuses:
        candidates = ScheduledPublication.objects.filter(
            generic_filter,
            status=publication_status,
            publication_key__startswith="ai:",
        )

        if (
            publication_status == ScheduledPublication.STATUS_QUEUED
            and min_lead_minutes
        ):
            candidates = candidates.filter(
                scheduled_for__gt=(
                    now + timedelta(minutes=min_lead_minutes)
                )
            )

        candidate_ids = (
            candidates
            .exclude(
                caption_recovery__status=(
                    CreatorCaptionRecoveryState.STATUS_COMPLETED
                )
            )
            .order_by("scheduled_for", "pk")
            .values_list("pk", flat=True)
        )

        for publication_id in candidate_ids.iterator(
            chunk_size=100
        ):
            with transaction.atomic():
                publication = (
                    ScheduledPublication.objects
                    .select_for_update(skip_locked=True)
                    .select_related("creator")
                    .filter(
                        pk=publication_id,
                        status=publication_status,
                    )
                    .first()
                )

                if publication is None:
                    continue

                # Recheck timing after acquiring the row lock.
                # Candidate selection alone is insufficient.
                if (
                    publication_status
                    == ScheduledPublication.STATUS_QUEUED
                    and min_lead_minutes
                    and publication.scheduled_for
                    <= timezone.now()
                    + timedelta(minutes=min_lead_minutes)
                ):
                    continue

                if (
                    publication.creator.username.casefold()
                    not in approved_accounts
                ):
                    continue

                if not is_generic_publication(publication):
                    continue

                state, _ = (
                    CreatorCaptionRecoveryState.objects
                    .get_or_create(publication=publication)
                )

                if state.status == (
                    CreatorCaptionRecoveryState.STATUS_COMPLETED
                ):
                    continue

                if (
                    state.status
                    == CreatorCaptionRecoveryState.STATUS_PROCESSING
                    and state.lease_expires_at
                    and state.lease_expires_at > now
                ):
                    continue

                if (
                    state.next_retry_at
                    and state.next_retry_at > now
                ):
                    continue

                token = uuid.uuid4()

                state.status = (
                    CreatorCaptionRecoveryState.STATUS_PROCESSING
                )
                state.claim_token = token
                state.claimed_at = now
                state.lease_expires_at = (
                    now + timedelta(minutes=lease_minutes)
                )
                state.next_retry_at = None

                state.save(
                    update_fields=[
                        "status",
                        "claim_token",
                        "claimed_at",
                        "lease_expires_at",
                        "next_retry_at",
                        "updated_at",
                    ]
                )

                return publication.pk, token

    return None


def verify_claim(publication_id, token):
    """
    Return True only while this worker owns a live lease.
    """
    now = timezone.now()

    return (
        CreatorCaptionRecoveryState.objects
        .filter(
            publication_id=publication_id,
            status=CreatorCaptionRecoveryState.STATUS_PROCESSING,
            claim_token=token,
            lease_expires_at__gt=now,
        )
        .exists()
    )


def mark_recovery_failed(publication_id, token, error):
    """
    Release a failed claim and schedule exponential backoff.

    A stale worker cannot overwrite a newer claim.
    """
    with transaction.atomic():
        state = (
            CreatorCaptionRecoveryState.objects
            .select_for_update()
            .filter(
                publication_id=publication_id,
                status=CreatorCaptionRecoveryState.STATUS_PROCESSING,
                claim_token=token,
            )
            .first()
        )

        if state is None:
            return False

        now = timezone.now()

        if (
            state.lease_expires_at is None
            or state.lease_expires_at <= now
        ):
            return False

        state.attempt_count += 1

        delay = min(
            30 * (2 ** min(state.attempt_count - 1, 6)),
            1440,
        )

        state.status = (
            CreatorCaptionRecoveryState.STATUS_FAILED
        )
        state.last_error = str(error)[:2000]
        state.next_retry_at = (
            now + timedelta(minutes=delay)
        )
        state.claim_token = None
        state.claimed_at = None
        state.lease_expires_at = None

        state.save(
            update_fields=[
                "status",
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


def apply_recovery(
    publication_id,
    token,
    translations,
    hashtags,
    *,
    expected_title,
    expected_content,
    min_lead_minutes=0,
    expected_media_id=None,
    expected_media_name=None,
):
    """
    Atomically replace generic creator copy.

    No FeedPosts or publication records are created.
    Original text is retained for explicit rollback.
    """
    from django.core.management.base import CommandError

    from auctions.localization_fingerprint import (
        localization_fingerprint,
    )
    from auctions.management.commands.repair_creator_captions import (
        validate_recovery_translations,
    )
    from auctions.models import (
        FeedPost,
        FeedPostMedia,
        FeedPostLocalizationState,
        FeedPostTranslation,
    )

    if (expected_media_id is None) != (expected_media_name is None):
        raise CommandError(
            "Published media ID and filename must be supplied together."
        )

    validate_recovery_translations(
        translations,
        hashtags,
    )

    now = timezone.now()

    with transaction.atomic():
        # Match the claim path's lock order:
        # publication first, then recovery ledger.
        publication = (
            ScheduledPublication.objects
            .select_for_update()
            .select_related("creator")
            .get(pk=publication_id)
        )

        state = (
            CreatorCaptionRecoveryState.objects
            .select_for_update()
            .get(publication=publication)
        )

        if (
            state.status
            != CreatorCaptionRecoveryState.STATUS_PROCESSING
            or state.claim_token != token
            or state.lease_expires_at is None
            or state.lease_expires_at <= now
        ):
            raise CommandError(
                "Recovery claim expired or changed."
            )

        if (
            publication.title != expected_title
            or publication.content != expected_content
        ):
            raise CommandError(
                "Publication changed during recovery."
            )

        if not is_generic_publication(publication):
            raise CommandError(
                "Publication is no longer generic."
            )

        if publication.status not in ELIGIBLE_STATUSES:
            raise CommandError(
                "Publication is not ready for recovery."
            )

        if (
            min_lead_minutes
            and publication.status
            == ScheduledPublication.STATUS_QUEUED
            and publication.scheduled_for
            <= timezone.now()
            + timedelta(minutes=min_lead_minutes)
        ):
            raise CommandError(
                "Publication too close to scheduled release."
            )

        english = translations["en"]

        snapshot = {
            "publication": {
                "title": publication.title,
                "content": publication.content,
                "status": publication.status,
                "scheduled_for": (
                    publication.scheduled_for.isoformat()
                ),
            },
            "feed_post": None,
            "translations": {},
        }

        post = None

        if publication.status == (
            ScheduledPublication.STATUS_PUBLISHED
        ):
            if publication.feed_post_id is None:
                raise CommandError(
                    "Published publication has no FeedPost."
                )

            post = (
                FeedPost.objects
                .select_for_update()
                .get(pk=publication.feed_post_id)
            )

            if post.user_id != publication.creator_id:
                raise CommandError(
                    "Published FeedPost ownership mismatch."
                )

            if (
                post.title != expected_title
                or post.content != expected_content
            ):
                raise CommandError(
                    "Published FeedPost changed during recovery."
                )

            if expected_media_id is not None:
                primary_media = (
                    FeedPostMedia.objects
                    .select_for_update()
                    .filter(
                        post=post,
                        media_type=FeedPostMedia.MEDIA_TYPE_IMAGE,
                        is_active=True,
                    )
                    .order_by("display_order", "pk")
                    .first()
                )

                if (
                    primary_media is None
                    or primary_media.pk != expected_media_id
                    or primary_media.file.name != expected_media_name
                ):
                    raise CommandError(
                        "Published image changed during recovery."
                    )

            snapshot["feed_post"] = {
                "id": post.pk,
                "title": post.title,
                "content": post.content,
            }

            existing_rows = list(
                FeedPostTranslation.objects
                .select_for_update()
                .filter(post=post)
                .order_by("language", "pk")
            )

            snapshot["translations"] = {
                row.language: {
                    "id": row.pk,
                    "title": row.title,
                    "content": row.content,
                    "image": row.image.name if row.image else "",
                }
                for row in existing_rows
            }

        if state.original_snapshot is not None:
            raise CommandError(
                "Recovery snapshot already exists."
            )

        # Preserve the validated generated text separately
        # from the original rollback snapshot.
        state.original_snapshot = snapshot
        state.recovered_translations = {
            language: {
                "title": translations[language]["title"],
                "content": translations[language]["content"],
            }
            for language in ("en", "es", "pt")
        }

        publication.title = english["title"]
        publication.content = english["content"]
        publication.save(
            update_fields=[
                "title",
                "content",
                "updated_at",
            ]
        )

        if post is not None:
            post.title = english["title"]
            post.content = english["content"]
            post.save(
                update_fields=["title", "content"]
            )

            for language in ("en", "es", "pt"):
                data = translations[language]

                row, _ = (
                    FeedPostTranslation.objects
                    .get_or_create(
                        post=post,
                        language=language,
                    )
                )

                row.title = data["title"]
                row.content = data["content"]
                row.save(
                    update_fields=[
                        "title",
                        "content",
                        "updated_at",
                    ]
                )

            localization_state, _ = (
                FeedPostLocalizationState.objects
                .select_for_update()
                .get_or_create(post=post)
            )

            localization_state.audited_fingerprint = (
                localization_fingerprint(post)
            )
            localization_state.attempt_count = 0
            localization_state.last_error = ""
            localization_state.next_retry_at = None
            localization_state.last_attempt_at = now
            localization_state.save()

        state.status = (
            CreatorCaptionRecoveryState.STATUS_COMPLETED
        )
        state.completed_at = now
        state.claim_token = None
        state.claimed_at = None
        state.lease_expires_at = None
        state.next_retry_at = None
        state.last_error = ""
        state.save()

        return {
            "publication_id": publication.pk,
            "feed_post_id": post.pk if post else None,
            "status": "completed",
        }


def attach_recovered_translations(publication, post):
    """
    Attach previously recovered EN/ES/PT text to an existing FeedPost.

    Caller must hold the ScheduledPublication and FeedPost
    row locks inside a transaction.atomic() block.

    This function never creates a FeedPost.
    """
    from django.core.management.base import CommandError
    from django.db import connection

    from auctions.localization_fingerprint import (
        localization_fingerprint,
    )
    from auctions.management.commands.repair_creator_captions import (
        validate_recovery_translations,
    )
    from auctions.models import (
        FeedPostLocalizationState,
        FeedPostTranslation,
    )

    if not connection.in_atomic_block:
        raise CommandError(
            "Translation handoff requires an active transaction."
        )

    if publication.feed_post_id not in (None, post.pk):
        raise CommandError(
            "Publication is linked to a different FeedPost."
        )

    if post.user_id != publication.creator_id:
        raise CommandError(
            "Translation handoff creator mismatch."
        )

    state = (
        CreatorCaptionRecoveryState.objects
        .select_for_update()
        .filter(
            publication=publication,
            status=CreatorCaptionRecoveryState.STATUS_COMPLETED,
        )
        .first()
    )

    if state is None or not state.recovered_translations:
        return False

    translations = state.recovered_translations

    if not isinstance(translations, dict):
        raise CommandError(
            "Invalid recovered translation payload."
        )

    english = translations.get("en")

    if not isinstance(english, dict):
        raise CommandError(
            "Recovered English translation missing."
        )

    if (
        publication.title != english.get("title")
        or publication.content != english.get("content")
        or post.title != english.get("title")
        or post.content != english.get("content")
    ):
        raise CommandError(
            "Recovered translation source mismatch."
        )

    hashtags = (
        translations["en"]["content"]
        .split("\n\n")[-1]
        .strip()
        .split()
    )

    if len(hashtags) != 6:
        raise CommandError(
            "Recovered hashtag count mismatch."
        )

    validate_recovery_translations(
        translations,
        [tag.removeprefix("#") for tag in hashtags],
    )

    for language in ("en", "es", "pt"):
        data = translations[language]

        row, created = (
            FeedPostTranslation.objects
            .select_for_update()
            .get_or_create(
                post=post,
                language=language,
                defaults={
                    "title": data["title"],
                    "content": data["content"],
                },
            )
        )

        if not created and (
            row.title != data["title"]
            or row.content != data["content"]
        ):
            raise CommandError(
                f"Existing {language} translation conflicts "
                "with recovered content."
            )

    localization_state, _ = (
        FeedPostLocalizationState.objects
        .select_for_update()
        .get_or_create(post=post)
    )

    localization_state.audited_fingerprint = (
        localization_fingerprint(post)
    )
    localization_state.attempt_count = 0
    localization_state.last_error = ""
    localization_state.next_retry_at = None
    localization_state.last_attempt_at = timezone.now()
    localization_state.save()

    return True
