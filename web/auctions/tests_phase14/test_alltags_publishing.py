from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from tempfile import TemporaryDirectory

from auctions.alltags_publishing import (
    SUCCESS,
    publish_interactive_post,
)
from auctions.forms import FeedPostForm
from auctions.models import (
    AllTagsPromotion,
    BidWallet,
    FeedPost,
)
from auctions.utils import get_system_wallet


class AllTagsPublishingTests(TestCase):

    def setUp(self):
        self.temp_media = TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)

        self.media_override = override_settings(
            MEDIA_ROOT=self.temp_media.name,
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

        self.creator = User.objects.create_user(
            username="AllTagsPublishingTest",
            password="test-password",
        )

        self.wallet = BidWallet.objects.create(
            user=self.creator,
            credits=100,
        )

        self.platform = get_system_wallet()

    def make_form(self):
        buffer = BytesIO()
        Image.new("RGB", (32, 32)).save(
            buffer, format="PNG"
        )

        image = SimpleUploadedFile(
            "publishing.png",
            buffer.getvalue(),
            content_type="image/png",
        )

        return FeedPostForm(
            data={
                "title": "AllTags publishing test",
                "content": "A public image post.",
                "media_type": "image",
                "is_public": "on",
                "unlock_price": "0",
                "alltags_requested": "on",
            },
            files={"images": [image]},
            current_username=self.creator.username,
        )

    def test_successful_promotion(self):
        post, outcome = publish_interactive_post(
            form=self.make_form(),
            user=self.creator,
            alltags=True,
        )

        self.assertEqual(outcome, SUCCESS)
        self.assertTrue(post.is_public)
        self.assertFalse(post.is_paid)
        self.assertTrue(
            AllTagsPromotion.objects.filter(
                post=post,
            ).exists()
        )

        self.wallet.refresh_from_db()
        self.platform.refresh_from_db()

        self.assertEqual(self.wallet.credits, 80)
        self.assertEqual(self.platform.credits, 20)

    def test_insufficient_credits_fallback(self):
        self.wallet.credits = 10
        self.wallet.save(update_fields=["credits"])

        post, outcome = publish_interactive_post(
            form=self.make_form(),
            user=self.creator,
            alltags=True,
        )

        self.assertEqual(
            outcome,
            "Insufficient credits (no charge)",
        )
        self.assertTrue(
            FeedPost.objects.filter(pk=post.pk).exists()
        )
        self.assertFalse(
            AllTagsPromotion.objects.filter(
                post=post,
            ).exists()
        )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 10)

    def test_daily_limit_fallback(self):
        first, outcome = publish_interactive_post(
            form=self.make_form(),
            user=self.creator,
            alltags=True,
        )
        self.assertEqual(outcome, SUCCESS)

        second, outcome = publish_interactive_post(
            form=self.make_form(),
            user=self.creator,
            alltags=True,
        )

        self.assertEqual(
            outcome,
            "Daily limit reached (no charge)",
        )
        self.assertTrue(
            FeedPost.objects.filter(pk=second.pk).exists()
        )
        self.assertEqual(
            AllTagsPromotion.objects.count(), 1
        )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 80)


    def test_failure_removes_new_media(self):
        media_root = Path(self.temp_media.name)

        with patch(
            "auctions.alltags_publishing.sync_post_hashtags",
            side_effect=RuntimeError("Simulated failure"),
        ):
            with self.assertRaises(RuntimeError):
                publish_interactive_post(
                    form=self.make_form(),
                    user=self.creator,
                    alltags=True,
                )

        self.assertEqual(FeedPost.objects.count(), 0)
        self.assertEqual(AllTagsPromotion.objects.count(), 0)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 100)

        saved_files = [
            path
            for path in media_root.rglob("*")
            if path.is_file()
        ]

        self.assertEqual(saved_files, [])
