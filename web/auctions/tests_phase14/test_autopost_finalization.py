"""AutoPost finalization readiness tests."""

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from auctions.ai_services.autopost_finalization import (
    validate_autopost_ready,
    publish_ready_autopost,
)
from auctions.models import (
    AutoPostConfiguration,
    AutoPostPublication,
    PlatformMediaAsset,
)
from auctions.tests_phase14.autopost_entitlement_helpers import (
    grant_autopost_pilot,
)

TAGS = ["FANZ", "Creator", "Photo", "Life", "Art", "Explore"]


class AutoPostFinalizationTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        media = override_settings(MEDIA_ROOT=temp.name)
        media.enable()
        self.addCleanup(media.disable)

        self.user = get_user_model().objects.create_user(
            username="autopost_finalizer_creator",
        )
        grant_autopost_pilot(self.user)

        self.config = AutoPostConfiguration.objects.create(
            account=self.user,
            enabled=True,
            approved_hashtags=list(TAGS),
        )
        self.asset = PlatformMediaAsset.objects.create(
            account=self.user,
            sha256="f" * 64,
            image="platform/test.webp",
        )

        tag_line = " ".join(f"#{tag}" for tag in TAGS)
        self.publication = AutoPostPublication.objects.create(
            configuration=self.config,
            publication_key="autopost-finalizer-ready",
            sequence_number=1,
            media_asset=self.asset,
            scheduled_for=timezone.now() - timedelta(minutes=1),
            personality="snarky",
            suffix_translations={
                "en": "Stay curious.",
                "es": "Sigue explorando.",
                "pt": "Continue explorando.",
            },
            reserved_hashtags=list(TAGS),
            status=AutoPostPublication.STATUS_READY,
            translations={
                lang: {
                    "title": "Golden hour",
                    "content": (
                        "Beautiful moment.\n"
                        + {
                            "en": "Stay curious.",
                            "es": "Sigue explorando.",
                            "pt": "Continue explorando.",
                        }[lang]
                        + f"\n\n{tag_line}"
                    ),
                }
                for lang in ("en", "es", "pt")
            },
        )

    def test_ready_publication_passes(self):
        self.assertTrue(validate_autopost_ready(self.publication))

    def test_future_publication_rejected(self):
        self.publication.scheduled_for = (
            timezone.now() + timedelta(hours=1)
        )
        with self.assertRaises(ValidationError):
            validate_autopost_ready(self.publication)

    def test_missing_translation_rejected(self):
        del self.publication.translations["es"]
        with self.assertRaises(ValidationError):
            validate_autopost_ready(self.publication)

    def test_revoked_entitlement_rejected(self):
        from auctions.models import AutoPostEntitlement

        AutoPostEntitlement.objects.filter(
            account=self.user
        ).update(revoked_at=timezone.now())

        with self.assertRaises(ValidationError):
            validate_autopost_ready(self.publication)

    def test_wrong_account_media_rejected(self):
        other = get_user_model().objects.create_user(
            username="autopost_other_media_owner",
        )
        self.asset.account = other

        with self.assertRaises(ValidationError):
            validate_autopost_ready(self.publication)

    def test_tampered_personality_rejected(self):
        self.publication.translations["es"]["content"] = (
            self.publication.translations["es"]["content"]
            .replace("Sigue explorando.", "Different wording.")
        )

        with self.assertRaises(ValidationError):
            validate_autopost_ready(self.publication)

    def install_valid_image(self):
        from PIL import Image
        from django.core.files.base import ContentFile

        output = BytesIO()
        Image.new("RGB", (640, 800), (120, 140, 160)).save(
            output, format="JPEG"
        )
        self.asset.image.save(
            "autopost-source.jpg",
            ContentFile(output.getvalue()),
            save=True,
        )

    def test_ready_publication_creates_post_and_translations(self):
        from auctions.models import FeedPost, FeedPostTranslation

        self.install_valid_image()
        original_name = self.asset.image.name

        post = publish_ready_autopost(self.publication.pk)

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.status, "published")
        self.assertEqual(self.publication.feed_post_id, post.pk)
        self.assertEqual(FeedPost.objects.count(), 1)
        self.assertEqual(FeedPostTranslation.objects.count(), 3)
        self.assertEqual(
            set(post.translations.values_list("language", flat=True)),
            {"en", "es", "pt"},
        )
        self.assertTrue(self.asset.image.storage.exists(original_name))
        self.assertEqual(self.asset.image.name, original_name)
        self.assertTrue(post.media.exists())

    def test_repeated_publication_returns_same_post(self):
        from auctions.models import FeedPost

        self.install_valid_image()

        first = publish_ready_autopost(self.publication.pk)
        second = publish_ready_autopost(self.publication.pk)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(FeedPost.objects.count(), 1)

    def test_translation_failure_rolls_back_and_cleans_media(self):
        from auctions.models import FeedPost, FeedPostMedia, FeedPostTranslation

        self.install_valid_image()

        original_create = FeedPostTranslation.objects.create

        def fail_spanish(**kwargs):
            if kwargs["language"] == "es":
                raise RuntimeError("Simulated Spanish storage failure")
            return original_create(**kwargs)

        with patch.object(
            FeedPostTranslation.objects,
            "create",
            side_effect=fail_spanish,
        ):
            with self.assertRaises(RuntimeError):
                publish_ready_autopost(self.publication.pk)

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.status, "ready")
        self.assertIsNone(self.publication.feed_post_id)
        self.assertFalse(FeedPost.objects.exists())
        self.assertFalse(FeedPostMedia.objects.exists())
        self.assertFalse(FeedPostTranslation.objects.exists())
        self.assertTrue(self.asset.image.storage.exists(
            self.asset.image.name
        ))

        # Database rollback must also remove newly published media.
        media_root = Path(self.asset.image.storage.location)
        remaining = list((media_root / "feed").rglob("*.webp")) \
            if (media_root / "feed").exists() else []

        self.assertEqual(remaining, [])

    def test_future_publication_creates_no_feed_post(self):
        from auctions.models import FeedPost

        self.install_valid_image()
        self.publication.scheduled_for = (
            timezone.now() + timedelta(hours=1)
        )
        self.publication.save(update_fields=["scheduled_for"])

        with self.assertRaises(ValidationError):
            publish_ready_autopost(self.publication.pk)

        self.assertFalse(FeedPost.objects.exists())

    def test_failure_preserves_existing_published_media(self):
        from auctions.models import FeedPostTranslation

        self.install_valid_image()

        first = publish_ready_autopost(self.publication.pk)
        original_media = first.media.get()
        original_name = original_media.file.name
        storage = original_media.file.storage

        self.assertTrue(storage.exists(original_name))

        self.publication.status = "ready"
        self.publication.feed_post = None
        self.publication.save(update_fields=["status", "feed_post"])

        with patch.object(
            FeedPostTranslation.objects,
            "create",
            side_effect=RuntimeError("Simulated failure"),
        ):
            with self.assertRaises(RuntimeError):
                publish_ready_autopost(self.publication.pk)

        self.assertTrue(storage.exists(original_name))
