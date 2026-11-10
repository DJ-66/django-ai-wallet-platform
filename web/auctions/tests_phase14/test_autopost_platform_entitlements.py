"""Platform-managed AutoPost authorization regression tests."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services.autopost_entitlements import (
    has_active_autopost_entitlement,
)
from auctions.models import AutoPostEntitlement, BidWallet, WalletTransaction
from auctions.utils import get_system_wallet


class AutoPostPlatformEntitlementTests(TestCase):
    def setUp(self):
        self.account = get_user_model().objects.create_user(
            username="platform_autopost_creator",
        )

        self.now = timezone.now()

    def grant(self, **overrides):
        values = {
            "account": self.account,
            "source": AutoPostEntitlement.SOURCE_PLATFORM,
            "reference": "platform:test-creator",
            "starts_at": self.now - timedelta(days=1),
            "expires_at": self.now + timedelta(days=30),
        }
        values.update(overrides)
        return AutoPostEntitlement.objects.create(**values)

    def test_active_platform_grant_authorizes(self):
        self.grant()
        self.assertTrue(
            has_active_autopost_entitlement(
                account_id=self.account.pk
            )
        )

    def test_revoked_platform_grant_rejected(self):
        self.grant(revoked_at=self.now)
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.account.pk
            )
        )

    def test_expired_platform_grant_rejected(self):
        self.grant(
            starts_at=self.now - timedelta(days=31),
            expires_at=self.now - timedelta(days=1),
        )
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.account.pk
            )
        )

    def test_future_platform_grant_rejected(self):
        self.grant(
            starts_at=self.now + timedelta(days=1),
            expires_at=self.now + timedelta(days=31),
        )
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.account.pk
            )
        )

    def test_platform_grant_cannot_reference_payment(self):
        sender = BidWallet.objects.create(
            user=self.account,
            credits=500,
        )
        receiver = get_system_wallet()

        payment = WalletTransaction.objects.create(
            sender=sender,
            receiver=receiver,
            amount=150,
            transaction_type="autopost_subscription",
            reference="platform:invalid-payment-test",
        )

        entitlement = AutoPostEntitlement(
            account=self.account,
            source=AutoPostEntitlement.SOURCE_PLATFORM,
            reference="platform:invalid-payment",
            starts_at=self.now - timedelta(days=1),
            expires_at=self.now + timedelta(days=30),
            payment_transaction=payment,
        )

        with self.assertRaises(ValidationError):
            entitlement.full_clean()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                entitlement.save()

        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.account.pk
            )
        )
