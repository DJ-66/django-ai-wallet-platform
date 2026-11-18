import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services.creator_publishing_attempts import (
    claim_publishing_attempt,
    complete_publishing_attempt,
    create_attempt_for_locked_publication,
    validate_locked_publishing_attempt,
    verify_publishing_attempt,
)
from auctions.management.commands.process_scheduled_publications import Command
from auctions.models import (
    CreatorPublishingAttempt,
    FeedPost,
    PlatformMediaAsset,
    ScheduledPublication,
)


User = get_user_model()


class CreatorPublishingAttemptTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="AttemptCreator",
        )

        self.publication = ScheduledPublication.objects.create(
            publication_key="ai:attemptcreator:test",
            creator=self.creator,
            source_path="creator.jpg",
            title="Attempt title",
            content="Attempt caption.",
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_PUBLISHING,
        )

    def mark_published(self):
        post = FeedPost.objects.create(
            user=self.creator,
            title="Published title",
            content="Published creator caption.",
            is_public=True,
        )

        self.publication.feed_post = post
        self.publication.status = (
            ScheduledPublication.STATUS_PUBLISHED
        )
        self.publication.published_at = timezone.now()
        self.publication.save(
            update_fields=[
                "feed_post",
                "status",
                "published_at",
            ]
        )

        return post

    def test_completion_succeeds_for_published_post(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )
        post = self.mark_published()

        attempt = complete_publishing_attempt(
            attempt_id,
            token,
        )

        self.assertEqual(
            attempt.status,
            CreatorPublishingAttempt.STATUS_COMPLETED,
        )
        self.assertIsNotNone(attempt.completed_at)

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.feed_post_id, post.pk)
        self.assertEqual(
            self.publication.status,
            ScheduledPublication.STATUS_PUBLISHED,
        )

    def test_completion_rejects_wrong_token(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )
        self.mark_published()

        with self.assertRaisesRegex(
            RuntimeError,
            "ownership mismatch",
        ):
            complete_publishing_attempt(
                attempt_id,
                uuid.uuid4(),
            )

        self.assertEqual(
            CreatorPublishingAttempt.objects.get(
                pk=attempt_id
            ).status,
            CreatorPublishingAttempt.STATUS_ACTIVE,
        )

    def test_completion_rejects_expired_lease(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )
        self.mark_published()

        CreatorPublishingAttempt.objects.filter(
            pk=attempt_id,
        ).update(
            lease_expires_at=(
                timezone.now() - timedelta(seconds=1)
            )
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "expired",
        ):
            complete_publishing_attempt(attempt_id, token)

        self.assertEqual(
            CreatorPublishingAttempt.objects.get(
                pk=attempt_id
            ).status,
            CreatorPublishingAttempt.STATUS_ACTIVE,
        )

    def test_completion_rejects_unpublished_post(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Cannot complete an unpublished",
        ):
            complete_publishing_attempt(attempt_id, token)

        self.assertEqual(
            CreatorPublishingAttempt.objects.get(
                pk=attempt_id
            ).status,
            CreatorPublishingAttempt.STATUS_ACTIVE,
        )

    def test_completion_cannot_run_twice(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )
        self.mark_published()

        complete_publishing_attempt(attempt_id, token)

        with self.assertRaisesRegex(
            RuntimeError,
            "ownership mismatch",
        ):
            complete_publishing_attempt(attempt_id, token)

        self.assertEqual(
            FeedPost.objects.filter(user=self.creator).count(),
            1,
        )

    def test_locked_attempt_rolls_back_with_claim(self):
        original_attempt_count = self.publication.attempt_count

        with self.assertRaisesRegex(
            RuntimeError,
            "Simulated claim transaction failure",
        ):
            with transaction.atomic():
                publication = (
                    ScheduledPublication.objects
                    .select_for_update()
                    .get(pk=self.publication.pk)
                )

                publication.attempt_count += 1
                publication.save(
                    update_fields=[
                        "attempt_count",
                        "updated_at",
                    ]
                )

                result = create_attempt_for_locked_publication(
                    publication,
                )

                self.assertIsNotNone(result)
                self.assertTrue(
                    CreatorPublishingAttempt.objects.filter(
                        pk=result[0],
                    ).exists()
                )

                raise RuntimeError(
                    "Simulated claim transaction failure"
                )

        self.publication.refresh_from_db()

        self.assertEqual(
            self.publication.attempt_count,
            original_attempt_count,
        )
        self.assertEqual(
            self.publication.status,
            ScheduledPublication.STATUS_PUBLISHING,
        )
        self.assertFalse(
            CreatorPublishingAttempt.objects.filter(
                publication=self.publication,
            ).exists()
        )

    def test_locked_validator_rejects_wrong_token(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )

        with transaction.atomic():
            publication = (
                ScheduledPublication.objects
                .select_for_update()
                .get(pk=self.publication.pk)
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "ownership mismatch",
            ):
                validate_locked_publishing_attempt(
                    publication,
                    attempt_id,
                    uuid.uuid4(),
                )

    def test_locked_validator_rejects_expired_lease(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )

        CreatorPublishingAttempt.objects.filter(
            pk=attempt_id,
        ).update(
            lease_expires_at=(
                timezone.now() - timedelta(seconds=1)
            )
        )

        with transaction.atomic():
            publication = (
                ScheduledPublication.objects
                .select_for_update()
                .get(pk=self.publication.pk)
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "expired",
            ):
                validate_locked_publishing_attempt(
                    publication,
                    attempt_id,
                    token,
                )

    def test_locked_validator_rejects_invalid_publication(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )

        self.publication.status = (
            ScheduledPublication.STATUS_FAILED
        )
        self.publication.save(update_fields=["status"])

        with transaction.atomic():
            publication = (
                ScheduledPublication.objects
                .select_for_update()
                .get(pk=self.publication.pk)
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "not eligible",
            ):
                validate_locked_publishing_attempt(
                    publication,
                    attempt_id,
                    token,
                )

    def test_locked_validator_accepts_live_owner(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )

        with transaction.atomic():
            publication = (
                ScheduledPublication.objects
                .select_for_update()
                .get(pk=self.publication.pk)
            )

            attempt = validate_locked_publishing_attempt(
                publication,
                attempt_id,
                token,
            )

            self.assertEqual(attempt.pk, attempt_id)
            self.assertEqual(attempt.token, token)
            self.assertEqual(
                attempt.status,
                CreatorPublishingAttempt.STATUS_ACTIVE,
            )

    def test_locked_publication_creates_attempt(self):
        with transaction.atomic():
            publication = (
                ScheduledPublication.objects
                .select_for_update()
                .get(pk=self.publication.pk)
            )

            result = create_attempt_for_locked_publication(
                publication,
            )

            self.assertIsNotNone(result)
            attempt_id, token = result

        attempt = CreatorPublishingAttempt.objects.get(
            pk=attempt_id,
        )

        self.assertEqual(
            attempt.publication_id,
            self.publication.pk,
        )
        self.assertEqual(attempt.token, token)
        self.assertEqual(
            attempt.status,
            CreatorPublishingAttempt.STATUS_ACTIVE,
        )
        self.assertTrue(
            verify_publishing_attempt(attempt_id, token)
        )

    def test_stale_worker_cannot_fail_new_attempt(self):
        old_attempt_id, old_token = claim_publishing_attempt(
            self.publication.pk
        )

        CreatorPublishingAttempt.objects.filter(
            pk=old_attempt_id,
        ).update(
            status=CreatorPublishingAttempt.STATUS_ABANDONED,
            lease_expires_at=(
                timezone.now() - timedelta(seconds=1)
            ),
        )

        new_claim = claim_publishing_attempt(
            self.publication.pk
        )

        self.assertIsNotNone(new_claim)
        new_attempt_id, new_token = new_claim

        command = Command()

        changed = command._mark_creator_failed(
            self.publication.pk,
            old_attempt_id,
            old_token,
            "Stale worker failure",
        )

        self.assertFalse(changed)

        self.publication.refresh_from_db()

        self.assertEqual(
            self.publication.status,
            ScheduledPublication.STATUS_PUBLISHING,
        )
        self.assertEqual(self.publication.last_error, "")

        old_attempt = CreatorPublishingAttempt.objects.get(
            pk=old_attempt_id,
        )
        new_attempt = CreatorPublishingAttempt.objects.get(
            pk=new_attempt_id,
        )

        self.assertEqual(
            old_attempt.status,
            CreatorPublishingAttempt.STATUS_ABANDONED,
        )
        self.assertEqual(
            new_attempt.status,
            CreatorPublishingAttempt.STATUS_ACTIVE,
        )
        self.assertEqual(new_attempt.token, new_token)
        self.assertTrue(
            verify_publishing_attempt(
                new_attempt_id,
                new_token,
            )
        )

    def test_claim_creates_durable_attempt(self):
        result = claim_publishing_attempt(self.publication.pk)

        self.assertIsNotNone(result)
        attempt_id, token = result

        attempt = CreatorPublishingAttempt.objects.get(
            pk=attempt_id,
        )

        self.assertEqual(attempt.token, token)
        self.assertEqual(
            attempt.status,
            CreatorPublishingAttempt.STATUS_ACTIVE,
        )
        self.assertEqual(
            attempt.publication_id,
            self.publication.pk,
        )
        self.assertIn(str(token), attempt.media_namespace)
        self.assertTrue(
            verify_publishing_attempt(attempt_id, token)
        )

    def test_duplicate_active_claim_is_rejected(self):
        first = claim_publishing_attempt(self.publication.pk)

        self.assertIsNotNone(first)
        self.assertIsNone(
            claim_publishing_attempt(self.publication.pk)
        )
        self.assertEqual(
            CreatorPublishingAttempt.objects.count(),
            1,
        )

    def test_wrong_token_is_rejected(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )

        self.assertTrue(
            verify_publishing_attempt(attempt_id, token)
        )
        self.assertFalse(
            verify_publishing_attempt(attempt_id, uuid.uuid4())
        )

    def test_expired_lease_is_rejected(self):
        attempt_id, token = claim_publishing_attempt(
            self.publication.pk
        )

        CreatorPublishingAttempt.objects.filter(
            pk=attempt_id,
        ).update(
            lease_expires_at=timezone.now() - timedelta(seconds=1)
        )

        self.assertFalse(
            verify_publishing_attempt(attempt_id, token)
        )

    def test_promotional_publication_cannot_claim(self):
        asset = PlatformMediaAsset.objects.create(
            account=self.creator,
            image="platform_media/attempt-test.jpg",
            sha256="b" * 64,
        )

        self.publication.media_asset = asset
        self.publication.save(update_fields=["media_asset"])

        self.assertIsNone(
            claim_publishing_attempt(self.publication.pk)
        )
        self.assertFalse(
            CreatorPublishingAttempt.objects.exists()
        )

    def test_queued_publication_cannot_claim(self):
        self.publication.status = ScheduledPublication.STATUS_QUEUED
        self.publication.save(update_fields=["status"])

        self.assertIsNone(
            claim_publishing_attempt(self.publication.pk)
        )
        self.assertFalse(
            CreatorPublishingAttempt.objects.exists()
        )
