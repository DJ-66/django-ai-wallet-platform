from django.test import SimpleTestCase
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services import creator_caption_recovery as recovery
from auctions.models import (
    CreatorCaptionRecoveryState,
    FeedPost,
    FeedPostTranslation,
    FeedPostMedia,
    ScheduledPublication,
)


User = get_user_model()

HASHTAGS = [
    "Fashion",
    "Lifestyle",
    "Style",
    "Confidence",
    "AIInfluencer",
    "FANZ",
]


def translated_copy():
    hashtags = " ".join(f"#{tag}" for tag in HASHTAGS)

    return {
        "en": {
            "title": "Coffee and Chaos",
            "content": (
                "One espresso became three."
                + "\n\n"
                + hashtags
            ),
        },
        "es": {
            "title": "Café y caos",
            "content": (
                "Un café se convirtió en tres."
                + "\n\n"
                + hashtags
            ),
        },
        "pt": {
            "title": "Café e caos",
            "content": (
                "Um café virou três."
                + "\n\n"
                + hashtags
            ),
        },
    }


class CreatorCaptionRecoveryApplyTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.manifest = Path(self.tempdir.name) / "manifest.json"
        self.manifest.write_text(json.dumps({
            "creators": [{"account": "CreatorA"}],
        }))

        self.creator = User.objects.create_user(
            username="CreatorA",
        )

        self.publication = ScheduledPublication.objects.create(
            publication_key="ai:creatora:apply",
            creator=self.creator,
            source_path="creator.jpg",
            title="From the Collection",
            content="A new favorite from the collection.",
            scheduled_for=timezone.now() + timedelta(hours=1),
            status=ScheduledPublication.STATUS_QUEUED,
        )

    def claim(self):
        with patch(
            "auctions.management.commands."
            "generate_ai_publications.MANIFEST_PATH",
            self.manifest,
        ):
            return recovery.claim_next_publication()

    def test_queued_recovery_updates_existing_publication(self):
        original_id = self.publication.pk
        original_time = self.publication.scheduled_for
        original_title = self.publication.title
        original_content = self.publication.content

        publication_id, token = self.claim()

        result = recovery.apply_recovery(
            publication_id,
            token,
            translated_copy(),
            HASHTAGS,
            expected_title=original_title,
            expected_content=original_content,
        )

        self.publication.refresh_from_db()

        self.assertEqual(
            self.publication.pk,
            original_id,
        )
        self.assertEqual(
            self.publication.scheduled_for,
            original_time,
        )
        self.assertEqual(
            self.publication.title,
            "Coffee and Chaos",
        )

        self.assertEqual(
            self.publication.status,
            ScheduledPublication.STATUS_QUEUED,
        )

        self.assertIsNone(self.publication.feed_post_id)

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )

        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_COMPLETED,
        )

        self.assertEqual(
            state.original_snapshot["publication"]["title"],
            original_title,
        )

        self.assertEqual(
            state.recovered_translations,
            translated_copy(),
        )

        self.assertEqual(
            set(state.recovered_translations),
            {"en", "es", "pt"},
        )

        self.assertNotIn(
            "recovered_translations",
            state.original_snapshot,
        )

        self.assertEqual(
            state.original_snapshot["publication"]["content"],
            original_content,
        )

        self.assertEqual(result["status"], "completed")

    def test_published_recovery_preserves_post_identity(self):
        original_title = self.publication.title
        original_content = self.publication.content
        original_schedule = self.publication.scheduled_for

        post = FeedPost.objects.create(
            user=self.creator,
            title=original_title,
            content=original_content,
            is_public=True,
        )

        original_created_at = post.created_at
        original_user_id = post.user_id

        media = FeedPostMedia.objects.create(
            post=post,
            file="feed/media/recovery-test.jpg",
            media_type=FeedPostMedia.MEDIA_TYPE_IMAGE,
            is_active=True,
            display_order=0,
        )

        original_media_id = media.pk
        original_media_name = media.file.name

        english = FeedPostTranslation.objects.create(
            post=post,
            language="en",
            title=original_title,
            content=original_content,
        )

        self.publication.status = (
            ScheduledPublication.STATUS_PUBLISHED
        )
        self.publication.feed_post = post
        self.publication.published_at = timezone.now()
        self.publication.save(
            update_fields=[
                "status",
                "feed_post",
                "published_at",
            ]
        )

        original_published_at = (
            self.publication.published_at
        )

        publication_id, token = self.claim()

        result = recovery.apply_recovery(
            publication_id,
            token,
            translated_copy(),
            HASHTAGS,
            expected_title=original_title,
            expected_content=original_content,
        )

        self.publication.refresh_from_db()
        post.refresh_from_db()
        english.refresh_from_db()

        self.assertEqual(
            self.publication.status,
            ScheduledPublication.STATUS_PUBLISHED,
        )
        self.assertEqual(
            self.publication.feed_post_id,
            post.pk,
        )
        self.assertEqual(
            self.publication.scheduled_for,
            original_schedule,
        )
        self.assertEqual(
            self.publication.published_at,
            original_published_at,
        )
        self.assertEqual(
            post.created_at,
            original_created_at,
        )
        self.assertEqual(post.user_id, original_user_id)

        media.refresh_from_db()

        self.assertEqual(media.pk, original_media_id)
        self.assertEqual(
            media.file.name,
            original_media_name,
        )
        self.assertTrue(media.is_active)
        self.assertEqual(media.display_order, 0)
        self.assertEqual(
            post.title,
            "Coffee and Chaos",
        )
        self.assertEqual(
            english.title,
            "Coffee and Chaos",
        )

        self.assertEqual(
            FeedPost.objects.filter(pk=post.pk).count(),
            1,
        )

        translations = {
            row.language: row
            for row in FeedPostTranslation.objects.filter(
                post=post,
            )
        }

        self.assertEqual(
            set(translations),
            {"en", "es", "pt"},
        )

        for language, data in translated_copy().items():
            self.assertEqual(
                translations[language].title,
                data["title"],
            )
            self.assertEqual(
                translations[language].content,
                data["content"],
            )

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )

        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_COMPLETED,
        )
        self.assertEqual(
            state.original_snapshot["feed_post"]["id"],
            post.pk,
        )
        self.assertEqual(
            state.original_snapshot["translations"]["en"]["id"],
            english.pk,
        )
        self.assertEqual(
            state.recovered_translations,
            translated_copy(),
        )
        self.assertEqual(
            result["feed_post_id"],
            post.pk,
        )

    def test_published_translation_failure_rolls_back_all(self):
        original_title = self.publication.title
        original_content = self.publication.content

        post = FeedPost.objects.create(
            user=self.creator,
            title=original_title,
            content=original_content,
            is_public=True,
        )

        self.publication.status = (
            ScheduledPublication.STATUS_PUBLISHED
        )
        self.publication.feed_post = post
        self.publication.published_at = timezone.now()
        self.publication.save(
            update_fields=[
                "status",
                "feed_post",
                "published_at",
            ]
        )

        publication_id, token = self.claim()

        original_save = FeedPostTranslation.save

        def fail_portuguese(instance, *args, **kwargs):
            if instance.language == "pt":
                raise RuntimeError(
                    "Simulated Portuguese save failure"
                )
            return original_save(instance, *args, **kwargs)

        with patch.object(
            FeedPostTranslation,
            "save",
            autospec=True,
            side_effect=fail_portuguese,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Simulated Portuguese save failure",
            ):
                recovery.apply_recovery(
                    publication_id,
                    token,
                    translated_copy(),
                    HASHTAGS,
                    expected_title=original_title,
                    expected_content=original_content,
                )

        self.publication.refresh_from_db()
        post.refresh_from_db()

        self.assertEqual(
            self.publication.title,
            original_title,
        )
        self.assertEqual(
            self.publication.content,
            original_content,
        )
        self.assertEqual(post.title, original_title)
        self.assertEqual(post.content, original_content)

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
            CreatorCaptionRecoveryState.STATUS_PROCESSING,
        )
        self.assertIsNone(state.original_snapshot)
        self.assertIsNone(state.recovered_translations)
        self.assertEqual(state.claim_token, token)
        self.assertIsNone(state.completed_at)

        self.assertTrue(
            recovery.verify_claim(publication_id, token)
        )


    def test_pre_apply_deadline_rejects_late_recovery(self):
        publication = self.publication

        publication.scheduled_for = (
            timezone.now() + timedelta(minutes=3)
        )
        publication.save(update_fields=["scheduled_for"])

        publication_id, token = self.claim()

        original_title = publication.title
        original_content = publication.content

        with self.assertRaisesMessage(
            Exception,
            "Publication too close to scheduled release.",
        ):
            recovery.apply_recovery(
                publication_id,
                token,
                translated_copy(),
                HASHTAGS,
                expected_title=original_title,
                expected_content=original_content,
                min_lead_minutes=5,
            )

        publication.refresh_from_db()

        state = CreatorCaptionRecoveryState.objects.get(
            publication=publication,
        )

        self.assertEqual(publication.title, original_title)
        self.assertEqual(publication.content, original_content)
        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_PROCESSING,
        )
        self.assertIsNone(state.original_snapshot)
        self.assertIsNone(state.recovered_translations)

    def test_expired_claim_cannot_apply(self):
        original_title = self.publication.title
        original_content = self.publication.content

        publication_id, token = self.claim()

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )
        state.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        state.save(update_fields=["lease_expires_at"])

        with self.assertRaisesMessage(
            Exception,
            "Recovery claim expired or changed.",
        ):
            recovery.apply_recovery(
                publication_id,
                token,
                translated_copy(),
                HASHTAGS,
                expected_title=original_title,
                expected_content=original_content,
            )

        self.publication.refresh_from_db()
        state.refresh_from_db()

        self.assertEqual(self.publication.title, original_title)
        self.assertEqual(self.publication.content, original_content)
        self.assertIsNone(state.original_snapshot)
        self.assertIsNone(state.recovered_translations)
        self.assertFalse(
            recovery.verify_claim(publication_id, token)
        )

    def test_reclaimed_claim_rejects_old_token(self):
        original_title = self.publication.title
        original_content = self.publication.content

        publication_id, old_token = self.claim()

        state = CreatorCaptionRecoveryState.objects.get(
            publication=self.publication,
        )
        state.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        state.save(update_fields=["lease_expires_at"])

        new_claim = self.claim()

        self.assertIsNotNone(new_claim)
        self.assertEqual(new_claim[0], publication_id)
        self.assertNotEqual(new_claim[1], old_token)

        with self.assertRaisesMessage(
            Exception,
            "Recovery claim expired or changed.",
        ):
            recovery.apply_recovery(
                publication_id,
                old_token,
                translated_copy(),
                HASHTAGS,
                expected_title=original_title,
                expected_content=original_content,
            )

        self.publication.refresh_from_db()
        state.refresh_from_db()

        self.assertEqual(self.publication.title, original_title)
        self.assertEqual(self.publication.content, original_content)
        self.assertEqual(state.claim_token, new_claim[1])
        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_PROCESSING,
        )
        self.assertIsNone(state.original_snapshot)
        self.assertTrue(
            recovery.verify_claim(*new_claim)
        )


class RecoveryMediaArgumentTests(SimpleTestCase):
    def test_media_identity_arguments_must_be_paired(self):
        from django.core.management.base import CommandError

        from auctions.ai_services.creator_caption_recovery import (
            apply_recovery,
        )

        for media_id, media_name in (
            (123, None),
            (None, "feed/media/image.jpg"),
        ):
            with self.subTest(
                media_id=media_id,
                media_name=media_name,
            ):
                with self.assertRaisesMessage(
                    CommandError,
                    "Published media ID and filename must be supplied together.",
                ):
                    apply_recovery(
                        123,
                        "unused-token",
                        {},
                        [],
                        expected_title="Original",
                        expected_content="Original",
                        expected_media_id=media_id,
                        expected_media_name=media_name,
                    )
