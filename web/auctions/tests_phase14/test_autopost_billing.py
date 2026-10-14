"""Database tests for AutoPost Pro credit billing."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from auctions.ai_services.autopost_billing import (
    purchase_autopost_subscription,
)
from auctions.models import (
    AutoPostEntitlement,
    BidWallet,
    WalletTransaction,
)
from auctions.utils import get_system_wallet


class AutoPostBillingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="autopost_billing_creator"
        )
        self.wallet = BidWallet.objects.create(
            user=self.user,
            credits=500,
        )
        self.platform_wallet = get_system_wallet()
        self.platform_wallet.credits = 1000
        self.platform_wallet.save(update_fields=["credits"])

    def balances(self):
        self.wallet.refresh_from_db()
        self.platform_wallet.refresh_from_db()
        return self.wallet.credits, self.platform_wallet.credits

    def test_successful_purchase_charges_150_once(self):
        entitlement, created = purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )

        self.assertTrue(created)
        self.assertEqual(self.balances(), (350, 1150))
        self.assertEqual(entitlement.source, "paid")
        self.assertEqual(
            entitlement.payment_transaction.transaction_type,
            "autopost_subscription",
        )
        self.assertEqual(
            entitlement.payment_transaction.amount,
            150,
        )
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_type="autopost_subscription"
            ).count(),
            1,
        )

    def test_retry_returns_existing_without_second_charge(self):
        first, created = purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )
        second, created_again = purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.balances(), (350, 1150))
        self.assertEqual(AutoPostEntitlement.objects.count(), 1)
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_type="autopost_subscription"
            ).count(),
            1,
        )

    def test_insufficient_credits_does_not_charge(self):
        self.wallet.credits = 149
        self.wallet.save(update_fields=["credits"])

        with self.assertRaises(ValidationError):
            purchase_autopost_subscription(
                account=self.user,
                period_key="2026-10",
            )

        self.assertEqual(self.balances(), (149, 1000))
        self.assertFalse(AutoPostEntitlement.objects.exists())
        self.assertFalse(
            WalletTransaction.objects.filter(
                transaction_type="autopost_subscription"
            ).exists()
        )

    def test_active_subscription_blocks_second_period(self):
        purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )

        with self.assertRaises(ValidationError):
            purchase_autopost_subscription(
                account=self.user,
                period_key="2026-11",
            )

        self.assertEqual(self.balances(), (350, 1150))
        self.assertEqual(AutoPostEntitlement.objects.count(), 1)

    def test_entitlement_failure_rolls_back_payment(self):
        with patch.object(
            AutoPostEntitlement.objects,
            "create",
            side_effect=RuntimeError("Simulated database failure"),
        ):
            with self.assertRaises(RuntimeError):
                purchase_autopost_subscription(
                    account=self.user,
                    period_key="2026-10",
                )

        self.assertEqual(self.balances(), (500, 1000))
        self.assertFalse(AutoPostEntitlement.objects.exists())
        self.assertFalse(
            WalletTransaction.objects.filter(
                transaction_type="autopost_subscription"
            ).exists()
        )
