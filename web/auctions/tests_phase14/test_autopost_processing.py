"""AutoPost processing claim regression tests."""

from datetime import timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from auctions.ai_services.autopost_processing import (
    claim_autopost,
    verify_autopost_claim,
    complete_autopost,
    fail_autopost,
)
from auctions.models import (
    AutoPostConfiguration,
    AutoPostPublication,
    PlatformMediaAsset,
)


class AutoPostProcessingTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        media = override_settings(MEDIA_ROOT=temp.name)
        media.enable()
        self.addCleanup(media.disable)

        self.account = get_user_model().objects.create_user(
            username="autopost_processing_creator",
        )

        self.config = AutoPostConfiguration.objects.create(
            account=self.account,
            enabled=True,
            personality="snarky",
        )

        asset = PlatformMediaAsset(
            account=self.account,
            sha256="d" * 64,
        )
        asset.image.save(
            "processing.webp",
            ContentFile(b"test-media"),
            save=True,
        )

        self.publication = AutoPostPublication.objects.create(
            configuration=self.config,
            publication_key="autopost-processing-test",
            sequence_number=1,
            media_asset=asset,
            scheduled_for=timezone.now() + timedelta(hours=12),
            personality="snarky",
            suffix_translations={
                "en": "Stay curious.",
                "es": "Sigue explorando.",
                "pt": "Continue explorando.",
            },
        )

    def test_claim_and_verify(self):
        result = claim_autopost()
        self.assertIsNotNone(result)

        publication_id, token = result

        self.assertEqual(publication_id, self.publication.pk)
        self.assertTrue(
            verify_autopost_claim(publication_id, token)
        )

    def test_second_claim_does_not_duplicate(self):
        self.assertIsNotNone(claim_autopost())
        self.assertIsNone(claim_autopost())

    def test_expired_claim_can_be_reclaimed(self):
        old_id, old_token = claim_autopost()

        AutoPostPublication.objects.filter(
            pk=old_id
        ).update(
            lease_expires_at=timezone.now() - timedelta(seconds=1),
        )

        new_id, new_token = claim_autopost()

        self.assertEqual(old_id, new_id)
        self.assertNotEqual(old_token, new_token)
        self.assertFalse(
            verify_autopost_claim(old_id, old_token)
        )
        self.assertTrue(
            verify_autopost_claim(new_id, new_token)
        )

    def test_disabled_configuration_is_skipped(self):
        self.config.enabled = False
        self.config.save(update_fields=["enabled"])

        self.assertIsNone(claim_autopost())

    def test_failure_schedules_retry(self):
        publication_id, token = claim_autopost()

        self.assertTrue(
            fail_autopost(publication_id, token, "Gemma timeout")
        )

        self.publication.refresh_from_db()

        self.assertEqual(self.publication.status, "failed")
        self.assertEqual(self.publication.attempt_count, 1)
        self.assertIsNotNone(self.publication.next_retry_at)
        self.assertIsNone(claim_autopost())

    def test_stale_worker_cannot_complete(self):
        publication_id, old_token = claim_autopost()

        AutoPostPublication.objects.filter(
            pk=publication_id
        ).update(
            lease_expires_at=timezone.now() - timedelta(seconds=1)
        )

        _, new_token = claim_autopost()

        self.assertNotEqual(old_token, new_token)
        self.assertFalse(
            complete_autopost(
                publication_id, old_token, {}, [],
            )
        )

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.status, "processing")
        self.assertIsNone(self.publication.translations)

    def test_stale_worker_cannot_mark_failure(self):
        publication_id, old_token = claim_autopost()

        AutoPostPublication.objects.filter(
            pk=publication_id
        ).update(
            lease_expires_at=timezone.now() - timedelta(seconds=1)
        )

        _, new_token = claim_autopost()

        self.assertFalse(
            fail_autopost(publication_id, old_token, "Late timeout")
        )
        self.assertTrue(
            verify_autopost_claim(publication_id, new_token)
        )

    def valid_translations(self):
        tags = ["FANZ", "Creator", "Photo", "Life", "Art", "Explore"]
        tag_line = " ".join("#" + tag for tag in tags)
        translations = {
            lang: {
                "title": f"Golden hour {lang}",
                "content": f"Beautiful moment {lang}.\n\n{tag_line}",
            }
            for lang in ("en", "es", "pt")
        }
        return translations, tags

    def test_valid_completion_persists_three_languages(self):
        publication_id, token = claim_autopost()
        translations, tags = self.valid_translations()

        self.assertTrue(
            complete_autopost(publication_id, token, translations, tags)
        )

        self.publication.refresh_from_db()

        self.assertEqual(self.publication.status, "ready")
        self.assertEqual(self.publication.translations, translations)
        self.assertIsNone(self.publication.claim_token)
        self.assertIsNone(self.publication.lease_expires_at)

    def test_invalid_completion_does_not_mark_ready(self):
        publication_id, token = claim_autopost()
        translations, tags = self.valid_translations()

        translations["es"]["content"] = "Missing hashtags"

        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            complete_autopost(
                publication_id, token, translations, tags
            )

        self.publication.refresh_from_db()

        self.assertEqual(self.publication.status, "processing")
        self.assertIsNone(self.publication.translations)
        self.assertEqual(self.publication.claim_token, token)

    def test_completed_publication_cannot_be_overwritten(self):
        publication_id, token = claim_autopost()
        translations, tags = self.valid_translations()

        self.assertTrue(
            complete_autopost(publication_id, token, translations, tags)
        )

        self.assertFalse(
            complete_autopost(publication_id, token, {}, [])
        )

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.status, "ready")
        self.assertEqual(self.publication.translations, translations)

    def test_far_future_reservation_is_not_claimed(self):
        self.publication.scheduled_for = (
            timezone.now() + timedelta(days=5)
        )
        self.publication.save(update_fields=["scheduled_for"])

        self.assertIsNone(claim_autopost())

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.status, "reserved")
        self.assertIsNone(self.publication.claim_token)
