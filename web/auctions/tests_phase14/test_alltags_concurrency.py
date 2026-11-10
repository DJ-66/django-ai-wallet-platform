from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase

from auctions.alltags_services import purchase_alltags_promotion
from auctions.models import (
    AllTagsPromotion,
    BidWallet,
    FeedPost,
    WalletTransaction,
)
from auctions.utils import get_system_wallet


class AllTagsConcurrencyTests(TransactionTestCase):

    def test_two_simultaneous_purchases_charge_once(self):
        creator = User.objects.create_user(
            username="ConcurrentAllTags",
            password="test-password",
        )

        wallet = BidWallet.objects.create(
            user=creator,
            credits=100,
        )

        platform = get_system_wallet()

        posts = [
            FeedPost.objects.create(
                user=creator,
                content=f"Concurrent image post {i}",
                image=f"feed/concurrent-{i}.webp",
                is_public=True,
                is_paid=False,
            )
            for i in range(2)
        ]

        barrier = Barrier(2)

        def attempt(post_id):
            close_old_connections()

            try:
                barrier.wait(timeout=10)

                post = FeedPost.objects.get(pk=post_id)
                user = User.objects.get(pk=creator.pk)

                purchase_alltags_promotion(
                    creator=user,
                    post=post,
                )

                return "SUCCESS"

            except ValidationError:
                return "REJECTED"

            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    attempt,
                    [post.pk for post in posts],
                )
            )

        wallet.refresh_from_db()
        platform.refresh_from_db()

        self.assertEqual(results.count("SUCCESS"), 1)
        self.assertEqual(results.count("REJECTED"), 1)

        self.assertEqual(wallet.credits, 80)
        self.assertEqual(platform.credits, 20)

        self.assertEqual(
            AllTagsPromotion.objects.count(),
            1,
        )

        self.assertEqual(
            WalletTransaction.objects.filter(
                reference__startswith="alltags:post:"
            ).count(),
            1,
        )
