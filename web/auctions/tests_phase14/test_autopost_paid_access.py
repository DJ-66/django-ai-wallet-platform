"""Verified paid entitlement authorization tests."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services.autopost_billing import purchase_autopost_subscription
from auctions.ai_services.autopost_entitlements import (
    has_active_autopost_entitlement,
)
from auctions.models import AutoPostEntitlement, BidWallet, WalletTransaction
from auctions.utils import get_system_wallet


class AutoPostPaidAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="autopost_paid_access_creator"
        )
        self.wallet = BidWallet.objects.create(user=self.user, credits=500)
        self.platform_wallet = get_system_wallet()

    def test_verified_paid_purchase_grants_access(self):
        entitlement, created = purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )
        self.assertTrue(created)
        self.assertTrue(has_active_autopost_entitlement(account_id=self.user.pk))

    def test_tampered_payment_does_not_grant_access(self):
        entitlement, _ = purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )

        payment = entitlement.payment_transaction
        payment.amount = 149
        payment.save(update_fields=["amount"])

        self.assertFalse(
            has_active_autopost_entitlement(account_id=self.user.pk)
        )

    def test_wrong_payment_type_does_not_grant_access(self):
        entitlement, _ = purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )

        payment = entitlement.payment_transaction
        payment.transaction_type = "transfer"
        payment.save(update_fields=["transaction_type"])

        self.assertFalse(
            has_active_autopost_entitlement(account_id=self.user.pk)
        )

    def test_revoked_entitlement_does_not_grant_access(self):
        entitlement, _ = purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )

        entitlement.revoked_at = timezone.now()
        entitlement.save(update_fields=["revoked_at"])

        self.assertFalse(
            has_active_autopost_entitlement(account_id=self.user.pk)
        )

    def test_expired_entitlement_does_not_grant_access(self):
        entitlement, _ = purchase_autopost_subscription(
            account=self.user,
            period_key="2026-10",
        )

        future = timezone.now() + timedelta(days=31)
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.user.pk,
                at=future,
            )
        )
