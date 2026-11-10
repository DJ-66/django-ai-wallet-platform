import uuid
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from auctions.models import (
    AllTagsPromotion,
    BidWallet,
    FeedPost,
    WalletTransaction,
)


class AllTagsConfirmationTests(TestCase):

    def setUp(self):
        self.creator = User.objects.create_user(
            username="AllTagsConfirmationTest",
            password="test-password",
        )
        self.wallet = BidWallet.objects.create(
            user=self.creator,
            credits=100,
        )
        self.client.force_login(self.creator)

    def make_image(self):
        buffer = BytesIO()
        Image.new("RGB", (32, 32)).save(
            buffer,
            format="PNG",
        )
        return SimpleUploadedFile(
            "confirmation.png",
            buffer.getvalue(),
            content_type="image/png",
        )

    def test_unconfirmed_promotion_creates_nothing(self):
        response = self.client.post(
            reverse("feed_home"),
            data={
                "submission_token": str(uuid.uuid4()),
                "title": "Unconfirmed promotion",
                "content": "This should not publish.",
                "media_type": "image",
                "is_public": "on",
                "unlock_price": "0",
                "alltags_requested": "on",
                "images": [self.make_image()],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FeedPost.objects.count(), 0)
        self.assertEqual(AllTagsPromotion.objects.count(), 0)
        self.assertFalse(
            WalletTransaction.objects.filter(
                reference__startswith="alltags:post:"
            ).exists()
        )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 100)


    def test_confirmed_promotion_charges_20(self):
        response = self.client.post(
            reverse("feed_home"),
            data={
                "submission_token": str(uuid.uuid4()),
                "title": "Confirmed promotion",
                "content": "Public promotion test.",
                "media_type": "image",
                "is_public": "on",
                "unlock_price": "0",
                "alltags_requested": "on",
                "alltags_confirmed": "yes",
                "images": [self.make_image()],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FeedPost.objects.count(), 1)
        self.assertEqual(AllTagsPromotion.objects.count(), 1)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 80)

        self.assertContains(
            response,
            "Promotion Successful ! (You Paid 20 Credits)",
        )


    def test_insufficient_credits_http_fallback(self):
        self.wallet.credits = 10
        self.wallet.save(update_fields=["credits"])

        response = self.client.post(
            reverse("feed_home"),
            data={
                "submission_token": str(uuid.uuid4()),
                "title": "Insufficient credits fallback",
                "content": "Regular public post.",
                "media_type": "image",
                "is_public": "on",
                "unlock_price": "0",
                "alltags_requested": "on",
                "alltags_confirmed": "yes",
                "images": [self.make_image()],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FeedPost.objects.count(), 1)
        self.assertEqual(AllTagsPromotion.objects.count(), 0)

        post = FeedPost.objects.get()
        self.assertTrue(post.is_public)
        self.assertFalse(post.is_paid)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 10)

        self.assertContains(
            response,
            "Insufficient credits (no charge)",
        )

    def test_daily_limit_http_fallback(self):
        def publish(title):
            return self.client.post(
                reverse("feed_home"),
                data={
                    "submission_token": str(uuid.uuid4()),
                    "title": title,
                    "content": "Public image post.",
                    "media_type": "image",
                    "is_public": "on",
                    "unlock_price": "0",
                    "alltags_requested": "on",
                    "alltags_confirmed": "yes",
                    "images": [self.make_image()],
                },
                follow=True,
            )

        first = publish("First promotion")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(AllTagsPromotion.objects.count(), 1)

        second = publish("Daily limit fallback")

        self.assertEqual(second.status_code, 200)
        self.assertEqual(FeedPost.objects.count(), 2)
        self.assertEqual(AllTagsPromotion.objects.count(), 1)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 80)

        self.assertContains(
            second,
            "Daily limit reached (no charge)",
        )


    def test_identical_http_retry_charges_once(self):
        import uuid

        from auctions.models import FeedPostSubmission

        token = str(uuid.uuid4())

        def submit():
            return self.client.post(
                reverse("feed_home"),
                data={
                    "submission_token": token,
                    "title": "HTTP retry promotion",
                    "content": "One post and one charge.",
                    "media_type": "image",
                    "is_public": "on",
                    "unlock_price": "0",
                    "alltags_requested": "on",
                    "alltags_confirmed": "yes",
                    "images": [self.make_image()],
                },
                follow=True,
            )

        first = submit()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(FeedPost.objects.count(), 1)
        self.assertEqual(AllTagsPromotion.objects.count(), 1)

        second = submit()

        self.assertEqual(second.status_code, 200)

        self.assertEqual(FeedPost.objects.count(), 1)
        self.assertEqual(FeedPostSubmission.objects.count(), 1)
        self.assertEqual(AllTagsPromotion.objects.count(), 1)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 80)

        self.assertContains(
            second,
            "Promotion Successful ! (You Paid 20 Credits)",
        )


    def test_alternate_true_values_require_confirmation(self):
        from auctions.models import FeedPostSubmission

        for value in ("true", "True", "1", "yes"):
            with self.subTest(value=value):
                response = self.client.post(
                    reverse("feed_home"),
                    data={
                        "submission_token": str(uuid.uuid4()),
                        "title": "Unconfirmed alternate checkbox",
                        "content": "Must not publish.",
                        "media_type": "image",
                        "is_public": "on",
                        "unlock_price": "0",
                        "alltags_requested": value,
                        "images": [self.make_image()],
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(FeedPost.objects.count(), 0)
                self.assertEqual(AllTagsPromotion.objects.count(), 0)
                self.assertEqual(
                    FeedPostSubmission.objects.count(), 0
                )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 100)
