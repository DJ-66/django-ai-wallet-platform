from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.db import transaction
from django.utils import timezone

from auctions.alltags_services import purchase_alltags_promotion
from auctions.models import (
    AllTagsPromotion,
    BidWallet,
    FeedPost,
    WalletTransaction,
)
from auctions.utils import get_system_wallet


class AllTagsBillingTests(TestCase):

    def setUp(self):
        self.creator = User.objects.create_user(
            username="AllTagsCreator",
            password="test-password",
        )
        self.wallet = BidWallet.objects.create(
            user=self.creator,
            credits=100,
        )
        self.platform = get_system_wallet()

    def make_post(self):
        return FeedPost.objects.create(
            user=self.creator,
            content="Test public image post",
            image="feed/test-image.webp",
            is_public=True,
            is_paid=False,
        )

    def test_successful_purchase(self):
        post = self.make_post()

        promotion = purchase_alltags_promotion(
            creator=self.creator,
            post=post,
        )

        self.wallet.refresh_from_db()
        self.platform.refresh_from_db()

        self.assertEqual(self.wallet.credits, 80)
        self.assertEqual(self.platform.credits, 20)
        self.assertEqual(promotion.price_credits, 20)
        self.assertEqual(promotion.post_id, post.pk)
        self.assertEqual(
            promotion.wallet_transaction.amount,
            20,
        )

    def test_insufficient_credits(self):
        self.wallet.credits = 10
        self.wallet.save(update_fields=["credits"])

        with self.assertRaises(ValidationError):
            purchase_alltags_promotion(
                creator=self.creator,
                post=self.make_post(),
            )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 10)
        self.assertEqual(
            AllTagsPromotion.objects.count(),
            0,
        )

    def test_duplicate_purchase_rejected(self):
        post = self.make_post()

        purchase_alltags_promotion(
            creator=self.creator,
            post=post,
        )

        with self.assertRaises(ValidationError):
            purchase_alltags_promotion(
                creator=self.creator,
                post=post,
            )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.credits, 80)
        self.assertEqual(
            AllTagsPromotion.objects.count(),
            1,
        )

    def test_rolling_24_hour_limit(self):
        first = purchase_alltags_promotion(
            creator=self.creator,
            post=self.make_post(),
        )

        with self.assertRaises(ValidationError):
            purchase_alltags_promotion(
                creator=self.creator,
                post=self.make_post(),
            )

        AllTagsPromotion.objects.filter(
            pk=first.pk,
        ).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        second = purchase_alltags_promotion(
            creator=self.creator,
            post=self.make_post(),
        )

        self.assertIsNotNone(second.pk)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.credits, 60)
        self.assertEqual(
            AllTagsPromotion.objects.count(),
            2,
        )


    def test_other_creator_cannot_purchase(self):
        other = User.objects.create_user(
            username="OtherCreator",
            password="test-password",
        )

        post = self.make_post()

        with self.assertRaises(ValidationError):
            purchase_alltags_promotion(
                creator=other,
                post=post,
            )

        self.assertEqual(
            AllTagsPromotion.objects.count(), 0
        )

    def test_private_post_rejected(self):
        post = self.make_post()
        post.is_public = False
        post.save(update_fields=["is_public"])

        with self.assertRaises(ValidationError):
            purchase_alltags_promotion(
                creator=self.creator,
                post=post,
            )

        self.assertEqual(
            AllTagsPromotion.objects.count(), 0
        )

    def test_paid_post_rejected(self):
        post = self.make_post()
        post.is_paid = True
        post.save(update_fields=["is_paid"])

        with self.assertRaises(ValidationError):
            purchase_alltags_promotion(
                creator=self.creator,
                post=post,
            )

        self.assertEqual(
            AllTagsPromotion.objects.count(), 0
        )

    def test_text_only_post_rejected(self):
        post = self.make_post()
        post.image = ""
        post.save(update_fields=["image"])

        with self.assertRaises(ValidationError):
            purchase_alltags_promotion(
                creator=self.creator,
                post=post,
            )

        self.assertEqual(
            AllTagsPromotion.objects.count(), 0
        )

    def test_deleted_post_preserves_cooldown(self):
        post = self.make_post()

        promotion = purchase_alltags_promotion(
            creator=self.creator,
            post=post,
        )

        post.delete()

        promotion.refresh_from_db()
        self.assertIsNone(promotion.post_id)

        with self.assertRaises(ValidationError):
            purchase_alltags_promotion(
                creator=self.creator,
                post=self.make_post(),
            )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.credits, 80)
        self.assertEqual(
            AllTagsPromotion.objects.count(), 1
        )


    def test_outer_transaction_rollback(self):
        post = self.make_post()

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                purchase_alltags_promotion(
                    creator=self.creator,
                    post=post,
                )
                raise RuntimeError(
                    "Simulated publication failure"
                )

        self.wallet.refresh_from_db()
        self.platform.refresh_from_db()

        self.assertEqual(self.wallet.credits, 100)
        self.assertEqual(self.platform.credits, 0)
        self.assertEqual(
            AllTagsPromotion.objects.count(), 0
        )
        self.assertFalse(
            WalletTransaction.objects.filter(
                reference=f"alltags:post:{post.pk}"
            ).exists()
        )
