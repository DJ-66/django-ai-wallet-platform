"""Real PostgreSQL concurrency tests for FANZ signup referrals."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from auctions.models import BidWallet, WalletTransaction
from auctions.wallet_setup import provision_user_wallet


User = get_user_model()


class GuestReferralConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username="concurrent_referrer",
            email="referrer@example.com",
        )
        self.referrer_wallet = BidWallet.objects.create(
            user=self.referrer,
            credits=100,
            referral_code="CONCURRENT50",
            signup_bonus_given=True,
        )

        self.new_users = [
            User.objects.create_user(
                username=f"concurrent_guest_{n}",
                email=f"guest{n}@example.com",
            )
            for n in (1, 2)
        ]

    def test_two_guests_reward_same_referrer_without_lost_update(self):
        self.assertEqual(connection.vendor, "postgresql")

        barrier = Barrier(2)

        def register(user_id):
            close_old_connections()
            try:
                user = User.objects.get(pk=user_id)
                barrier.wait(timeout=10)

                wallet = provision_user_wallet(
                    user,
                    referral_code="CONCURRENT50",
                )
                return wallet.pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(register, user.pk)
                for user in self.new_users
            ]
            wallet_ids = [f.result(timeout=20) for f in futures]

        self.assertEqual(len(set(wallet_ids)), 2)

        self.referrer_wallet.refresh_from_db()
        self.assertEqual(self.referrer_wallet.credits, 200)

        self.assertEqual(
            WalletTransaction.objects.filter(
                receiver=self.referrer_wallet,
                transaction_type="commission",
            ).count(),
            2,
        )

        for user in self.new_users:
            wallet = BidWallet.objects.get(user=user)
            self.assertEqual(wallet.credits, 50)
            self.assertTrue(wallet.signup_bonus_given)
            self.assertTrue(wallet.referral_bonus_given)
            self.assertEqual(wallet.referred_by_id, self.referrer.pk)

    def test_repeat_provisioning_does_not_repeat_rewards(self):
        user = self.new_users[0]

        provision_user_wallet(
            user,
            referral_code="CONCURRENT50",
        )
        provision_user_wallet(
            user,
            referral_code="CONCURRENT50",
        )

        wallet = BidWallet.objects.get(user=user)
        self.referrer_wallet.refresh_from_db()

        self.assertEqual(wallet.credits, 50)
        self.assertEqual(self.referrer_wallet.credits, 150)

        self.assertEqual(
            WalletTransaction.objects.filter(
                receiver=wallet,
                transaction_type="bonus",
            ).count(),
            1,
        )
        self.assertEqual(
            WalletTransaction.objects.filter(
                receiver=self.referrer_wallet,
                transaction_type="commission",
            ).count(),
            1,
        )
