"""Regression tests for wallet transaction and on_commit safety."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TransactionTestCase

from auctions.models import BidWallet, WalletTransaction
from auctions.wallet_setup import provision_user_wallet


User = get_user_model()


class WalletCommitSafetyTests(TransactionTestCase):

    def setUp(self):
        self.referrer = User.objects.create_user(
            username="commit_referrer",
            email="commit_referrer@example.com",
        )
        self.referrer_wallet = BidWallet.objects.create(
            user=self.referrer,
            credits=100,
            referral_code="COMMITSAFE50",
            signup_bonus_given=True,
        )
        self.guest = User.objects.create_user(
            username="commit_guest",
            email="commit_guest@example.com",
        )

    @patch("auctions.wallet_setup._generate_wallet_qr_codes")
    @patch("auctions.wallet_setup.send_welcome_email")
    def test_outer_rollback_cancels_credits_and_callbacks(
        self, mock_email, mock_qr
    ):
        with self.assertRaisesMessage(
            RuntimeError, "forced rollback"
        ):
            with transaction.atomic():
                provision_user_wallet(
                    self.guest,
                    referral_code="COMMITSAFE50",
                )
                raise RuntimeError("forced rollback")

        self.assertFalse(
            BidWallet.objects.filter(user=self.guest).exists()
        )

        self.referrer_wallet.refresh_from_db()
        self.assertEqual(self.referrer_wallet.credits, 100)

        self.assertEqual(
            WalletTransaction.objects.count(), 0
        )

        mock_email.assert_not_called()
        mock_qr.assert_not_called()

    @patch("auctions.wallet_setup._generate_wallet_qr_codes")
    @patch("auctions.wallet_setup.send_welcome_email")
    def test_callbacks_run_only_after_outer_commit(
        self, mock_email, mock_qr
    ):
        with transaction.atomic():
            provision_user_wallet(self.guest)

            mock_email.assert_not_called()
            mock_qr.assert_not_called()

        mock_email.assert_called_once()
        mock_qr.assert_called_once()

        wallet = BidWallet.objects.get(user=self.guest)
        self.assertEqual(wallet.credits, 50)
        self.assertTrue(wallet.signup_bonus_given)

    @patch("auctions.wallet_setup._generate_wallet_qr_codes")
    @patch("auctions.wallet_setup.send_welcome_email")
    def test_callback_failures_do_not_reverse_credits(
        self, mock_email, mock_qr
    ):
        mock_email.side_effect = RuntimeError("email failed")
        mock_qr.side_effect = RuntimeError("QR failed")

        with self.assertLogs(
            "auctions.wallet_setup", level="ERROR"
        ) as logs:
            provision_user_wallet(
                self.guest,
                referral_code="COMMITSAFE50",
            )

        wallet = BidWallet.objects.get(user=self.guest)
        self.referrer_wallet.refresh_from_db()

        self.assertEqual(wallet.credits, 50)
        self.assertEqual(self.referrer_wallet.credits, 150)

        self.assertTrue(wallet.signup_bonus_given)
        self.assertTrue(wallet.referral_bonus_given)

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

        self.assertEqual(len(logs.output), 2)
        mock_email.assert_called_once()
        mock_qr.assert_called_once()

    @patch("auctions.wallet_setup._generate_wallet_qr_codes")
    @patch("auctions.wallet_setup.send_welcome_email")
    def test_repeat_provisioning_does_not_repeat_signup_bonus(
        self, mock_email, mock_qr
    ):
        provision_user_wallet(self.guest)
        provision_user_wallet(self.guest)

        wallet = BidWallet.objects.get(user=self.guest)

        self.assertEqual(wallet.credits, 50)
        self.assertEqual(
            WalletTransaction.objects.filter(
                receiver=wallet,
                transaction_type="bonus",
            ).count(),
            1,
        )

        mock_email.assert_called_once()
        self.assertEqual(mock_qr.call_count, 2)
