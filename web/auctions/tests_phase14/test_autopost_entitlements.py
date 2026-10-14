"""AutoPost entitlement access checks."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services.autopost_entitlements import (
    has_active_autopost_entitlement,
)
from auctions.models import AutoPostEntitlement


class AutoPostEntitlementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="entitlement_creator",
        )
        self.other = get_user_model().objects.create_user(
            username="entitlement_other",
        )
        self.now = timezone.now()

    def grant(self, **overrides):
        values = {
            "account": self.user,
            "source": AutoPostEntitlement.SOURCE_PILOT,
            "reference": "pilot:test:001",
            "starts_at": self.now - timedelta(days=1),
            "expires_at": self.now + timedelta(days=7),
        }
        values.update(overrides)
        return AutoPostEntitlement.objects.create(**values)

    def test_no_entitlement_rejected(self):
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.user.pk,
                at=self.now,
            )
        )

    def test_active_pilot_accepted(self):
        self.grant()
        self.assertTrue(
            has_active_autopost_entitlement(
                account_id=self.user.pk,
                at=self.now,
            )
        )

    def test_other_account_cannot_use_pilot(self):
        self.grant()
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.other.pk,
                at=self.now,
            )
        )

    def test_expired_pilot_rejected(self):
        self.grant(
            expires_at=self.now,
        )
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.user.pk,
                at=self.now,
            )
        )

    def test_future_pilot_rejected(self):
        self.grant(
            starts_at=self.now + timedelta(hours=1),
        )
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.user.pk,
                at=self.now,
            )
        )

    def test_revoked_pilot_rejected(self):
        self.grant(revoked_at=self.now)
        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.user.pk,
                at=self.now,
            )
        )

    def test_unverified_paid_record_rejected(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.grant(source=AutoPostEntitlement.SOURCE_PAID)

        self.assertFalse(
            has_active_autopost_entitlement(
                account_id=self.user.pk,
                at=self.now,
            )
        )

    def test_duplicate_reference_is_rejected(self):
        from django.db import IntegrityError, transaction

        self.grant()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.grant()

    def test_multiple_active_pilots_are_valid(self):
        self.grant()
        self.grant(reference="pilot:test:002")

        self.assertTrue(
            has_active_autopost_entitlement(
                account_id=self.user.pk,
                at=self.now,
            )
        )

    def test_pilot_with_payment_reference_is_not_authorized(self):
        from auctions.models import BidWallet, WalletTransaction

        wallet = BidWallet.objects.create(user=self.user)

        payment = WalletTransaction.objects.create(
            sender=wallet,
            transaction_type="purchase",
            amount=150,
            reference="test:incorrect-pilot-payment",
        )

        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.grant(payment_transaction=payment)

    def test_database_rejects_invalid_period(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.grant(
                    starts_at=self.now,
                    expires_at=self.now,
                )

    def test_database_rejects_paid_without_payment(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.grant(
                    source=AutoPostEntitlement.SOURCE_PAID,
                )

    def test_database_rejects_pilot_with_payment(self):
        from django.db import IntegrityError, transaction
        from auctions.models import BidWallet, WalletTransaction

        wallet = BidWallet.objects.create(user=self.user)
        payment = WalletTransaction.objects.create(
            sender=wallet,
            transaction_type="purchase",
            amount=150,
            reference="test:pilot-payment",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.grant(payment_transaction=payment)
