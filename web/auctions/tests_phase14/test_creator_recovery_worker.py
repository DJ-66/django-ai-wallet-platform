import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services import creator_caption_recovery
from auctions.management.commands import (
    process_creator_caption_recovery as worker,
)
from auctions.models import (
    CreatorCaptionRecoveryState,
    FeedPost,
    FeedPostMedia,
    FeedPostTranslation,
    ScheduledPublication,
)
from auctions.tests_phase14.test_creator_caption_recovery_apply import (
    HASHTAGS,
    translated_copy,
)


class CreatorRecoveryWorkerTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name)
        self.image = self.root / "creator.jpg"
        self.image.write_bytes(b"mock-image")

        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({
            "creators": [{
                "account": "CreatorA",
                "bio": "Fictional creator",
                "post_style": {
                    "hashtags": HASHTAGS,
                },
            }],
        }))

        self.creator = get_user_model().objects.create_user(
            username="CreatorA",
        )

        self.publication = ScheduledPublication.objects.create(
            publication_key="ai:creatora:worker-test",
            creator=self.creator,
            source_path="creator.jpg",
            title="From the Collection",
            content="A new favorite from the collection.",
            scheduled_for=timezone.now() + timedelta(hours=3),
            status=ScheduledPublication.STATUS_QUEUED,
        )

    def run_worker(self):
        with (
            patch(
                "auctions.management.commands."
                "generate_ai_publications.MANIFEST_PATH",
                self.manifest,
            ),
            patch.object(worker, "MANIFEST_PATH", self.manifest),
        ):
            call_command(
                "process_creator_caption_recovery",
                source_root=str(self.root),
            )

    def test_successful_recovery(self):
        with patch.object(
            worker,
            "generate_recovery_translations",
            return_value=(translated_copy(), HASHTAGS),
        ):
            self.run_worker()

        self.publication.refresh_from_db()

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )

        self.assertEqual(self.publication.title, "Coffee and Chaos")
        self.assertEqual(state.status, "completed")
        self.assertEqual(
            set(state.recovered_translations),
            {"en", "es", "pt"},
        )
        self.assertEqual(
            self.publication.status,
            ScheduledPublication.STATUS_QUEUED,
        )
        self.assertIsNone(self.publication.feed_post_id)

    def test_published_recovery_uses_existing_media(self):
        post = FeedPost.objects.create(
            user=self.creator,
            title=self.publication.title,
            content=self.publication.content,
            is_public=True,
        )

        media = FeedPostMedia.objects.create(
            post=post,
            file="feed/media/creator-test.jpg",
            media_type=FeedPostMedia.MEDIA_TYPE_IMAGE,
            is_active=True,
        )

        self.publication.status = ScheduledPublication.STATUS_PUBLISHED
        self.publication.feed_post = post
        self.publication.published_at = timezone.now()
        self.publication.save(
            update_fields=["status", "feed_post", "published_at"]
        )

        original_id = post.pk
        original_date = self.publication.published_at

        with (
            patch.object(
                worker,
                "generate_recovery_translations",
                return_value=(translated_copy(), HASHTAGS),
            ) as generate,
            patch.object(
                media.file.storage,
                "open",
                return_value=__import__("io").BytesIO(b"mock-image"),
            ),
        ):
            self.run_worker_published()

        post.refresh_from_db()
        self.publication.refresh_from_db()

        self.assertEqual(post.pk, original_id)
        self.assertEqual(post.title, "Coffee and Chaos")
        self.assertEqual(
            self.publication.published_at,
            original_date,
        )
        self.assertEqual(
            set(
                FeedPostTranslation.objects
                .filter(post=post)
                .values_list("language", flat=True)
            ),
            {"en", "es", "pt"},
        )
        self.assertEqual(generate.call_count, 1)
        self.assertTrue(
            FeedPostMedia.objects.filter(pk=media.pk).exists()
        )

    def run_worker_published(self):
        with (
            patch(
                "auctions.management.commands."
                "generate_ai_publications.MANIFEST_PATH",
                self.manifest,
            ),
            patch.object(worker, "MANIFEST_PATH", self.manifest),
        ):
            call_command(
                "process_creator_caption_recovery",
                scope="published",
                source_root=str(self.root),
            )

    def test_published_recovery_rejects_wrong_owner(self):
        other_user = get_user_model().objects.create_user(
            username="OtherCreator",
        )

        post = FeedPost.objects.create(
            user=other_user,
            title=self.publication.title,
            content=self.publication.content,
            is_public=True,
        )

        self.publication.status = ScheduledPublication.STATUS_PUBLISHED
        self.publication.feed_post = post
        self.publication.published_at = timezone.now()
        self.publication.save(
            update_fields=["status", "feed_post", "published_at"]
        )

        with patch.object(
            worker,
            "generate_recovery_translations",
        ) as generate:
            with self.assertRaisesMessage(
                CommandError,
                "Published FeedPost ownership mismatch.",
            ):
                self.run_worker_published()

        generate.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.title, "From the Collection")

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )
        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_FAILED,
        )

    def test_published_recovery_rejects_changed_image(self):
        import io

        post = FeedPost.objects.create(
            user=self.creator,
            title=self.publication.title,
            content=self.publication.content,
            is_public=True,
        )

        media = FeedPostMedia.objects.create(
            post=post,
            file="feed/media/changed-image.jpg",
            media_type=FeedPostMedia.MEDIA_TYPE_IMAGE,
            is_active=True,
        )

        self.publication.status = ScheduledPublication.STATUS_PUBLISHED
        self.publication.feed_post = post
        self.publication.published_at = timezone.now()
        self.publication.save(
            update_fields=["status", "feed_post", "published_at"]
        )

        original_title = post.title

        def change_image_during_inference(**kwargs):
            media.is_active = False
            media.save(update_fields=["is_active"])
            return translated_copy(), HASHTAGS

        with (
            patch.object(
                worker,
                "generate_recovery_translations",
                side_effect=change_image_during_inference,
            ),
            patch.object(
                media.file.storage,
                "open",
                return_value=io.BytesIO(b"mock-image"),
            ),
        ):
            with self.assertRaisesMessage(
                CommandError,
                "Published image changed during recovery.",
            ):
                self.run_worker_published()

        post.refresh_from_db()
        self.publication.refresh_from_db()

        self.assertEqual(post.title, original_title)
        self.assertEqual(
            self.publication.title,
            "From the Collection",
        )

        self.assertFalse(
            FeedPostTranslation.objects.filter(
                post=post,
            ).exists()
        )

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )

        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_FAILED,
        )
        self.assertIsNone(state.original_snapshot)
        self.assertIsNone(state.recovered_translations)

    def test_published_recovery_rejects_missing_media(self):
        post = FeedPost.objects.create(
            user=self.creator,
            title=self.publication.title,
            content=self.publication.content,
            is_public=True,
        )

        self.publication.status = ScheduledPublication.STATUS_PUBLISHED
        self.publication.feed_post = post
        self.publication.published_at = timezone.now()
        self.publication.save(
            update_fields=["status", "feed_post", "published_at"]
        )

        with patch.object(
            worker,
            "generate_recovery_translations",
        ) as generate:
            with self.assertRaisesMessage(
                CommandError,
                "Published image missing.",
            ):
                self.run_worker_published()

        generate.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(post.title, "From the Collection")

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )
        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_FAILED,
        )

    def test_no_eligible_publication(self):
        self.publication.scheduled_for = (
            timezone.now() + timedelta(minutes=10)
        )
        self.publication.save(update_fields=["scheduled_for"])

        with patch.object(
            worker,
            "generate_recovery_translations",
        ) as generate:
            self.run_worker()

        generate.assert_not_called()

        self.assertFalse(
            CreatorCaptionRecoveryState.objects.filter(
                publication=self.publication,
            ).exists()
        )

    def test_generation_failure_records_retry(self):
        with patch.object(
            worker,
            "generate_recovery_translations",
            side_effect=RuntimeError("Mock AI unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.run_worker()

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )

        self.assertEqual(state.status, "failed")
        self.assertEqual(state.attempt_count, 1)
        self.assertIsNotNone(state.next_retry_at)

        self.publication.refresh_from_db()
        self.assertEqual(
            self.publication.title,
            "From the Collection",
        )

    def test_expired_claim_does_not_apply(self):
        def expire_claim(**kwargs):
            state = CreatorCaptionRecoveryState.objects.get(
                publication=self.publication,
            )
            state.lease_expires_at = (
                timezone.now() - timedelta(seconds=1)
            )
            state.save(update_fields=["lease_expires_at"])
            return translated_copy(), HASHTAGS

        with patch.object(
            worker,
            "generate_recovery_translations",
            side_effect=expire_claim,
        ):
            with self.assertRaises(Exception):
                self.run_worker()

        self.publication.refresh_from_db()
        self.assertEqual(
            self.publication.title,
            "From the Collection",
        )

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )
        self.assertNotEqual(state.status, "completed")
        self.assertIsNone(state.recovered_translations)
