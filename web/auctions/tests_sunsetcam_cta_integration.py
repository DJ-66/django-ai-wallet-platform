"""Database integration tests for SunsetCam marketing CTAs."""

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from auctions.management.commands.process_sunsetcam_capture import (
    CAPTURE_COPY,
    Command,
)
from auctions.models import (
    FeedPost,
    FeedPostMedia,
    FeedPostTranslation,
    SunsetCamCapture,
    UserProfile,
)
from auctions.sunsetcam_cta import (
    decorate_sunsetcam_caption,
)


class SunsetCamCTAIntegrationTests(TestCase):

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        root = Path(self.temp.name)

        media = override_settings(
            MEDIA_ROOT=str(root / "media"),
        )
        media.enable()
        self.addCleanup(media.disable)

        self.source = root / "capture.jpg"

        Image.new(
            "RGB",
            (1280, 720),
            color=(230, 140, 60),
        ).save(self.source, format="JPEG")

        self.user = get_user_model().objects.create_user(
            username="SunsetCam",
        )

        self.profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
        )

        self.profile.is_platform_account = True
        self.profile.save(
            update_fields=["is_platform_account"],
        )

        self.now = datetime(
            2026, 11, 24, 12, 0,
            tzinfo=ZoneInfo("America/Asuncion"),
        )

        self.capture_type = SunsetCamCapture.CAPTURE_MIDDAY
        self.command = Command()

    def publish(self, when=None):
        return self.command._create_post(
            now_local=when or self.now,
            capture_type=self.capture_type,
            source_path=self.source,
        )

    def test_authorized_publication(self):
        post, created = self.publish()

        self.assertTrue(created)
        self.assertEqual(post.user_id, self.user.pk)
        self.assertTrue(post.is_public)
        self.assertFalse(post.is_paid)
        self.assertEqual(post.unlock_price, 0)

        capture = SunsetCamCapture.objects.get(post=post)

        expected = decorate_sunsetcam_caption(
            content=CAPTURE_COPY[self.capture_type]["en"][1],
            language="en",
            capture_number=capture.pk,
        )

        post.refresh_from_db()
        self.assertEqual(post.content, expected)

        self.assertEqual(
            FeedPostMedia.objects.filter(
                post=post,
                is_active=True,
            ).count(),
            1,
        )

    def test_all_translations_aligned(self):
        post, created = self.publish()
        self.assertTrue(created)

        capture = SunsetCamCapture.objects.get(post=post)

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

        for language, (title, content) in (
            CAPTURE_COPY[self.capture_type].items()
        ):
            with self.subTest(language=language):
                expected = decorate_sunsetcam_caption(
                    content=content,
                    language=language,
                    capture_number=capture.pk,
                )

                self.assertEqual(
                    translations[language].content,
                    expected,
                )

                self.assertEqual(
                    translations[language].title,
                    f"SunsetCam #{capture.pk} — {title}",
                )

                self.assertEqual(
                    expected.rsplit("\n\n", 1)[1],
                    content.rsplit("\n\n", 1)[1],
                )

        post.refresh_from_db()

        self.assertEqual(
            post.content,
            translations["en"].content,
        )

    def test_duplicate_capture_is_unchanged(self):
        post, created = self.publish()
        self.assertTrue(created)

        original = post.content

        before = (
            FeedPost.objects.count(),
            SunsetCamCapture.objects.count(),
            FeedPostMedia.objects.count(),
            FeedPostTranslation.objects.count(),
        )

        repeated, created = self.publish()

        self.assertFalse(created)
        self.assertEqual(repeated.pk, post.pk)
        self.assertEqual(repeated.content, original)

        after = (
            FeedPost.objects.count(),
            SunsetCamCapture.objects.count(),
            FeedPostMedia.objects.count(),
            FeedPostTranslation.objects.count(),
        )

        self.assertEqual(before, after)

    def test_non_platform_account_has_no_cta(self):
        self.profile.is_platform_account = False
        self.profile.save(
            update_fields=["is_platform_account"],
        )

        post, created = self.publish()
        self.assertTrue(created)

        post.refresh_from_db()

        self.assertEqual(
            post.content,
            CAPTURE_COPY[self.capture_type]["en"][1],
        )

        for translation in FeedPostTranslation.objects.filter(
            post=post,
        ):
            self.assertEqual(
                translation.content,
                CAPTURE_COPY[self.capture_type][
                    translation.language
                ][1],
            )

    def test_historical_publication_unchanged(self):
        historical = FeedPost.objects.create(
            user=self.user,
            title="Historical SunsetCam capture",
            content="Original historical caption",
            is_public=True,
        )

        SunsetCamCapture.objects.create(
            local_date=(self.now - timedelta(days=1)).date(),
            capture_type=self.capture_type,
            post=historical,
        )

        post, created = self.publish()
        self.assertTrue(created)
        self.assertNotEqual(post.pk, historical.pk)

        historical.refresh_from_db()

        self.assertEqual(
            historical.content,
            "Original historical caption",
        )

        self.assertEqual(
            historical.title,
            "Historical SunsetCam capture",
        )
