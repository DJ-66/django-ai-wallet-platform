"""Paid-only AutoPost processing regression tests."""

from datetime import timedelta
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from auctions.ai_services.autopost_billing import (
    purchase_autopost_subscription,
)
from auctions.ai_services.autopost_processing import claim_autopost
from auctions.models import (
    AutoPostConfiguration,
    AutoPostPublication,
    BidWallet,
    PlatformMediaAsset,
)


class AutoPostPaidClaimTests(TestCase):
    """Reuse the existing publication fixture with paid-only access."""

    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        media = override_settings(MEDIA_ROOT=temp.name)
        media.enable()
        self.addCleanup(media.disable)

        self.account = get_user_model().objects.create_user(
            username="autopost_paid_claim_creator",
        )

        self.config = AutoPostConfiguration.objects.create(
            account=self.account,
            enabled=True,
            personality="snarky",
        )

        asset = PlatformMediaAsset(
            account=self.account,
            sha256="e" * 64,
        )
        asset.image.save(
            "paid-claim.webp",
            ContentFile(b"test-media"),
            save=True,
        )

        self.publication = AutoPostPublication.objects.create(
            configuration=self.config,
            publication_key="autopost-paid-claim-test",
            sequence_number=1,
            media_asset=asset,
            scheduled_for=timezone.now() + timedelta(hours=12),
            personality="snarky",
            suffix_translations={
                "en": "Stay curious.",
                "es": "Sigue explorando.",
                "pt": "Continue explorando.",
            },
        )

        BidWallet.objects.create(
            user=self.account,
            credits=500,
        )

        self.entitlement, created = purchase_autopost_subscription(
            account=self.account,
            period_key="paid-claim-regression",
        )
        self.assertTrue(created)

    def test_verified_paid_claim(self):
        result = claim_autopost()

        self.assertIsNotNone(result)
        self.assertEqual(result[0], self.publication.pk)

    def test_revoked_paid_claim_rejected(self):
        self.entitlement.revoked_at = timezone.now()
        self.entitlement.save(update_fields=["revoked_at"])

        self.assertIsNone(claim_autopost())

    def test_tampered_paid_claim_rejected(self):
        payment = self.entitlement.payment_transaction
        payment.amount = 149
        payment.save(update_fields=["amount"])

        self.assertIsNone(claim_autopost())

    def test_expired_paid_claim_rejected(self):
        now = timezone.now()
        self.entitlement.starts_at = now - timedelta(days=31)
        self.entitlement.expires_at = now - timedelta(days=1)
        self.entitlement.save(
            update_fields=["starts_at", "expires_at"]
        )
        self.assertIsNone(claim_autopost())

    def test_wrong_payment_type_rejected(self):
        payment = self.entitlement.payment_transaction
        payment.transaction_type = "transfer"
        payment.save(update_fields=["transaction_type"])
        self.assertIsNone(claim_autopost())

    def test_wrong_payment_sender_rejected(self):
        from django.contrib.auth import get_user_model
        from auctions.models import BidWallet

        other = get_user_model().objects.create_user(
            username="autopost_wrong_payment_sender",
        )
        other_wallet = BidWallet.objects.create(
            user=other,
            credits=0,
        )

        payment = self.entitlement.payment_transaction
        payment.sender = other_wallet
        payment.save(update_fields=["sender"])

        self.assertIsNone(claim_autopost())

    def test_wrong_payment_recipient_rejected(self):
        from django.contrib.auth import get_user_model
        from auctions.models import BidWallet

        other = get_user_model().objects.create_user(
            username="autopost_wrong_payment_recipient",
        )
        other_wallet = BidWallet.objects.create(
            user=other,
            credits=0,
        )

        payment = self.entitlement.payment_transaction
        payment.receiver = other_wallet
        payment.save(update_fields=["receiver"])

        self.assertIsNone(claim_autopost())
