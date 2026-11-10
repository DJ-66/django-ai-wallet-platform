"""Database-backed idempotency for interactive FANZ feed posts."""

import re
import uuid

from django.core.exceptions import ValidationError

from .models import FeedPostSubmission


FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FeedSubmissionRejected(ValidationError):
    """A submission token cannot be accepted or reused."""


def validate_submission_identity(*, token, fingerprint):
    try:
        parsed_token = uuid.UUID(str(token))
    except (ValueError, TypeError, AttributeError) as exc:
        raise FeedSubmissionRejected(
            "Invalid submission token."
        ) from exc

    if not isinstance(fingerprint, str) or not FINGERPRINT_PATTERN.fullmatch(
        fingerprint
    ):
        raise FeedSubmissionRejected(
            "Invalid submission fingerprint."
        )

    return parsed_token


def verify_existing_submission(*, submission, creator, fingerprint):
    if submission.creator_id != creator.pk:
        raise FeedSubmissionRejected(
            "Submission token belongs to another creator."
        )

    if submission.request_fingerprint != fingerprint:
        raise FeedSubmissionRejected(
            "Submission token was reused with different content."
        )

    if submission.post_id is None:
        raise FeedSubmissionRejected(
            "This submission has already been consumed."
        )

    return (
        submission.post,
        submission.promotion_outcome or None,
    )



def publish_once(
    *,
    token,
    fingerprint,
    creator,
    form,
    alltags=False,
):
    """
    Atomically claim a submission token and publish once.

    A committed token cannot publish or charge again.
    """
    from django.db import IntegrityError, transaction

    from .alltags_publishing import publish_interactive_post

    parsed_token = validate_submission_identity(
        token=token,
        fingerprint=fingerprint,
    )

    saved_files = []

    def track_media(storage, name):
        saved_files.append((storage, name))

    try:
        with transaction.atomic(durable=True):
            return _publish_once_transaction(
                parsed_token=parsed_token,
                fingerprint=fingerprint,
                creator=creator,
                form=form,
                alltags=alltags,
                track_media=track_media,
            )
    except Exception:
        for storage, name in reversed(saved_files):
            try:
                storage.delete(name)
            except Exception:
                pass
        raise


def _publish_once_transaction(
    *,
    parsed_token,
    fingerprint,
    creator,
    form,
    alltags,
    track_media,
):
    from django.db import IntegrityError, transaction
    from .alltags_publishing import publish_interactive_post

    with transaction.atomic():
        try:
            with transaction.atomic():
                submission = FeedPostSubmission.objects.create(
                    token=parsed_token,
                    creator=creator,
                    request_fingerprint=fingerprint,
                )
        except IntegrityError:
            submission = FeedPostSubmission.objects.filter(
                token=parsed_token,
            ).first()

            if submission is None:
                raise

            return verify_existing_submission(
                submission=submission,
                creator=creator,
                fingerprint=fingerprint,
            )

        post, outcome = publish_interactive_post(
            form=form,
            user=creator,
            alltags=alltags,
            on_media_saved=track_media,
        )

        submission.post = post
        submission.promotion_outcome = outcome or ""
        submission.save(
            update_fields=[
                "post",
                "promotion_outcome",
            ]
        )

        return post, outcome



def find_completed_submission(
    *,
    token,
    fingerprint,
    creator,
):
    """
    Return an existing completed submission, or None.

    Never publish, charge credits, or claim tokens here.
    """
    parsed_token = validate_submission_identity(
        token=token,
        fingerprint=fingerprint,
    )

    submission = (
        FeedPostSubmission.objects
        .filter(token=parsed_token)
        .first()
    )

    if submission is None:
        return None

    return verify_existing_submission(
        submission=submission,
        creator=creator,
        fingerprint=fingerprint,
    )
