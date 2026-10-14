"""AutoPost reservation-to-ready integration tests."""

from datetime import timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from auctions.ai_services.autopost_runner import process_next_autopost
from auctions.models import (
    AutoPostConfiguration,
    AutoPostPublication,
    FeedPost,
    PlatformMediaAsset,
    ScheduledPublication,
)

from auctions.tests_phase14.test_autopost_pipeline import (
    FakeLocalization,
    FakeVision,
    HASHTAGS,
)


class AutoPostRunnerTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        media = override_settings(MEDIA_ROOT=temp.name)
        media.enable()
        self.addCleanup(media.disable)

        user = get_user_model().objects.create_user(
            username="autopost_runner_creator",
        )
        config = AutoPostConfiguration.objects.create(
            account=user,
            enabled=True,
            personality="snarky",
        )
        asset = PlatformMediaAsset(
            account=user,
            sha256="e" * 64,
        )
        asset.image.save(
            "runner.webp",
            ContentFile(b"fake-image"),
            save=True,
        )

        self.publication = AutoPostPublication.objects.create(
            configuration=config,
            publication_key="autopost-runner-test",
            sequence_number=1,
            media_asset=asset,
            scheduled_for=timezone.now() + timedelta(hours=12),
            personality="snarky",
            suffix_translations={
                "en": "Stay curious.",
                "es": "Sigue explorando.",
                "pt": "Continue explorando.",
            },
            reserved_hashtags=list(HASHTAGS),
        )

    def test_reservation_becomes_ready_without_publishing(self):
        result = process_next_autopost(
            vision_provider=FakeVision(),
            localization_provider=FakeLocalization(),
        )

        self.assertEqual(result["status"], "ready")

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.status, "ready")
        self.assertEqual(set(self.publication.translations), {"en", "es", "pt"})

        self.assertEqual(FeedPost.objects.count(), 0)
        self.assertEqual(ScheduledPublication.objects.count(), 0)

    def test_second_run_does_not_duplicate(self):
        self.assertEqual(
            process_next_autopost(
                    vision_provider=FakeVision(),
                localization_provider=FakeLocalization(),
            )["status"],
            "ready",
        )

        result = process_next_autopost(
            vision_provider=FakeVision(),
            localization_provider=FakeLocalization(),
        )

        self.assertEqual(result["status"], "none")
        self.assertEqual(AutoPostPublication.objects.count(), 1)

    def test_expired_lease_cannot_save_ai_results(self):
        from unittest.mock import patch

        from auctions.ai_services.autopost_pipeline import (
            generate_autopost_draft,
        )

        real_generate = generate_autopost_draft

        def expire_during_inference(**kwargs):
            result = real_generate(**kwargs)

            AutoPostPublication.objects.filter(
                pk=self.publication.pk
            ).update(
                lease_expires_at=(
                    timezone.now() - timedelta(seconds=1)
                )
            )

            return result

        with patch(
            "auctions.ai_services.autopost_runner.generate_autopost_draft",
            side_effect=expire_during_inference,
        ):
            result = process_next_autopost(
                    vision_provider=FakeVision(),
                localization_provider=FakeLocalization(),
            )

        self.assertEqual(result["status"], "stale")

        self.publication.refresh_from_db()

        self.assertEqual(self.publication.status, "processing")
        self.assertIsNone(self.publication.translations)
        self.assertIsNotNone(self.publication.claim_token)

        self.assertEqual(FeedPost.objects.count(), 0)
        self.assertEqual(ScheduledPublication.objects.count(), 0)

    def test_runner_uses_configured_account_hashtags(self):
        from auctions.tests_phase14.test_autopost_pipeline import HASHTAGS

        config = self.publication.configuration
        config.approved_hashtags = list(HASHTAGS)
        config.save(update_fields=["approved_hashtags"])

        result = process_next_autopost(
            vision_provider=FakeVision(),
            localization_provider=FakeLocalization(),
        )

        self.assertEqual(result["status"], "ready")

        self.publication.refresh_from_db()
        self.assertIn(
            "#FANZ",
            self.publication.translations["en"]["content"],
        )

    def test_missing_reserved_hashtags_rejected_before_vision(self):
        from unittest.mock import Mock

        self.publication.reserved_hashtags = []
        self.publication.save(update_fields=["reserved_hashtags"])

        vision = Mock()

        result = process_next_autopost(
            vision_provider=vision,
            localization_provider=FakeLocalization(),
        )

        self.assertEqual(result["status"], "failed")
        vision.generate.assert_not_called()

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.status, "failed")
