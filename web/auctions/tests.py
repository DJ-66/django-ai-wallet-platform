from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from .btcpay import (
    BTCPayError,
    create_invoice,
    get_invoice,
    get_store,
)


BTCPAY_TEST_SETTINGS = {
    "BTCPAY_URL": "https://pay.example.test",
    "BTCPAY_STORE_ID": "store123",
    "BTCPAY_API_KEY": "test-key",
    "BTCPAY_TIMEOUT": 15,
}


@override_settings(**BTCPAY_TEST_SETTINGS)
class BTCPayClientTests(SimpleTestCase):
    @patch("auctions.btcpay.requests.request")
    def test_get_store(self, request):
        response = Mock()
        response.json.return_value = {
            "id": "store123",
            "name": "Fanz_Platform",
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        result = get_store()

        self.assertEqual(result["name"], "Fanz_Platform")

        args, kwargs = request.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(
            args[1],
            "https://pay.example.test/api/v1/stores/store123",
        )
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "token test-key",
        )

    @patch("auctions.btcpay.requests.request")
    def test_create_invoice(self, request):
        response = Mock()
        response.json.return_value = {
            "id": "invoice123",
            "status": "New",
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        result = create_invoice(
            amount="5.00",
            currency="USD",
            metadata={
                "purpose": "integration_test",
                "source": "FANZ",
            },
        )

        self.assertEqual(result["id"], "invoice123")

        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(kwargs["json"]["amount"], "5.00")
        self.assertEqual(
            kwargs["json"]["metadata"]["purpose"],
            "integration_test",
        )

    @patch("auctions.btcpay.requests.request")
    def test_get_invoice(self, request):
        response = Mock()
        response.json.return_value = {
            "id": "invoice123",
            "status": "New",
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        result = get_invoice("invoice123")

        self.assertEqual(result["status"], "New")

    def test_create_invoice_rejects_zero(self):
        with self.assertRaises(ValueError):
            create_invoice(amount="0")

    @override_settings(BTCPAY_API_KEY="")
    def test_missing_configuration_is_rejected(self):
        with self.assertRaises(BTCPayError):
            get_store()


from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import (
    BidWallet,
    CreditPackage,
    CreditPurchase,
    EconomyAsset,
    EconomyAssetDelivery,
    FounderAccount,
    PaymentIntent,
)
from .payment_services import (
    PaymentFulfillmentError,
    fulfill_payment_intent,
)


class PaymentFulfillmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="payment-test-user",
            password="test-password",
        )

        self.package = CreditPackage.objects.create(
            name="Test Package",
            credits=100,
            price_usd="5.00",
            is_active=True,
        )

    def create_settled_credit_intent(self):
        return PaymentIntent.objects.create(
            user=self.user,
            purpose="credit_purchase",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="test-btcpay-invoice",
            credit_package=self.package,
            paid_at=timezone.now(),
        )

    def test_credit_purchase_fulfillment(self):
        intent = self.create_settled_credit_intent()

        fulfilled, created = fulfill_payment_intent(intent.pk)

        self.assertTrue(created)
        self.assertEqual(fulfilled.status, "fulfilled")
        self.assertIsNotNone(fulfilled.fulfilled_at)

        wallet = BidWallet.objects.get(user=self.user)
        self.assertEqual(wallet.credits, 100)

        purchase = CreditPurchase.objects.get(
            external_id="btcpay:test-btcpay-invoice"
        )
        self.assertEqual(purchase.package, self.package)

    def test_credit_purchase_is_idempotent(self):
        intent = self.create_settled_credit_intent()

        fulfill_payment_intent(intent.pk)
        fulfilled, created = fulfill_payment_intent(intent.pk)

        self.assertFalse(created)

        wallet = BidWallet.objects.get(user=self.user)
        self.assertEqual(wallet.credits, 100)

        self.assertEqual(
            CreditPurchase.objects.filter(
                external_id="btcpay:test-btcpay-invoice"
            ).count(),
            1,
        )

        self.assertEqual(fulfilled.status, "fulfilled")

    def test_unsettled_payment_cannot_be_fulfilled(self):
        intent = PaymentIntent.objects.create(
            user=self.user,
            purpose="credit_purchase",
            status="processing",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="processing-invoice",
            credit_package=self.package,
        )

        with self.assertRaises(PaymentFulfillmentError):
            fulfill_payment_intent(intent.pk)

        self.assertFalse(
            CreditPurchase.objects.filter(
                external_id="btcpay:processing-invoice"
            ).exists()
        )

    def test_donation_mints_no_credits(self):
        intent = PaymentIntent.objects.create(
            user=self.user,
            purpose="donation",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="donation-invoice",
            paid_at=timezone.now(),
        )

        fulfilled, created = fulfill_payment_intent(intent.pk)

        self.assertTrue(created)
        self.assertEqual(fulfilled.status, "fulfilled")
        self.assertIsNotNone(fulfilled.fulfilled_at)

        self.assertFalse(
            CreditPurchase.objects.filter(
                external_id="btcpay:donation-invoice"
            ).exists()
        )

    def test_unhandled_payment_purpose_is_rejected(self):
        intent = PaymentIntent.objects.create(
            user=self.user,
            purpose="founder_purchase",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="unhandled-purpose-invoice",
            paid_at=timezone.now(),
        )

        with self.assertRaises(PaymentFulfillmentError):
            fulfill_payment_intent(intent.pk)

        intent.refresh_from_db()

        self.assertEqual(intent.status, "settled")
        self.assertIsNone(intent.fulfilled_at)

    def test_failed_fulfillment_does_not_mark_intent_fulfilled(self):
        intent = PaymentIntent.objects.create(
            user=self.user,
            purpose="platform_service",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="failed-fulfillment-invoice",
            paid_at=timezone.now(),
        )

        with self.assertRaises(PaymentFulfillmentError):
            fulfill_payment_intent(intent.pk)

        intent.refresh_from_db()

        self.assertEqual(intent.status, "settled")
        self.assertIsNone(intent.fulfilled_at)


class EconomyAssetModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="economy-asset-test-user",
            password="test-password",
        )

        self.founder = FounderAccount.objects.create(
            handle="eco1",
            current_account=self.user,
            owner_root=self.user,
            status=FounderAccount.STATUS_OWNED,
        )

    def test_founder_account_has_at_most_one_economy_asset(self):
        EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Eco1Fanz",
            symbol="ECO1FANZ",
        )

        with self.assertRaises(IntegrityError):
            EconomyAsset.objects.create(
                founder_account=self.founder,
                name="SecondEco1Fanz",
                symbol="ECO1SECOND",
            )

    def test_delivery_amount_must_be_positive(self):
        asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Eco1Fanz",
            symbol="ECO1FANZ",
        )

        intent = PaymentIntent.objects.create(
            user=self.user,
            purpose="platform_service",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="economy-zero-delivery",
            paid_at=timezone.now(),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EconomyAssetDelivery.objects.create(
                    asset=asset,
                    payment_intent=intent,
                    recipient_address="0x1234",
                    amount_base_units=0,
                )

    def test_default_supply_is_21_billion_at_six_decimals(self):
        asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Eco1Fanz",
            symbol="ECO1FANZ",
        )

        self.assertEqual(asset.decimals, 6)
        self.assertEqual(
            asset.genesis_supply_base_units,
            21_000_000_000_000_000,
        )



class EconomyAssetFulfillmentBridgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="economy-bridge-user",
            password="test-password",
        )

        self.founder = FounderAccount.objects.create(
            handle="eco2",
            current_account=self.user,
            owner_root=self.user,
            status=FounderAccount.STATUS_OWNED,
        )

        self.asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Eco2Fanz",
            symbol="ECO2FANZ",
            status=EconomyAsset.STATUS_ACTIVE,
        )

    def create_purchase_intent(self):
        return PaymentIntent.objects.create(
            user=self.user,
            purpose="economy_asset_purchase",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="economy-asset-purchase-invoice",
            metadata={
                "economy_asset_id": self.asset.pk,
                "recipient_address": "0x1234",
                "amount_base_units": 1_000_000,
            },
            paid_at=timezone.now(),
        )

    def test_settled_purchase_creates_one_pending_delivery(self):
        intent = self.create_purchase_intent()

        returned, completed = fulfill_payment_intent(intent.pk)

        self.assertFalse(completed)
        self.assertEqual(returned.status, "settled")
        self.assertIsNone(returned.fulfilled_at)

        delivery = EconomyAssetDelivery.objects.get(
            payment_intent=intent,
        )

        self.assertEqual(delivery.asset, self.asset)
        self.assertEqual(delivery.status, "pending")
        self.assertEqual(delivery.recipient_address, "0x1234")
        self.assertEqual(delivery.amount_base_units, 1_000_000)

        # Retry must reuse the same durable obligation.
        fulfill_payment_intent(intent.pk)

        self.assertEqual(
            EconomyAssetDelivery.objects.filter(
                payment_intent=intent,
            ).count(),
            1,
        )

    def test_invalid_metadata_creates_no_delivery(self):
        intent = PaymentIntent.objects.create(
            user=self.user,
            purpose="economy_asset_purchase",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="economy-invalid-metadata",
            metadata={},
            paid_at=timezone.now(),
        )

        with self.assertRaises(PaymentFulfillmentError):
            fulfill_payment_intent(intent.pk)

        intent.refresh_from_db()

        self.assertEqual(intent.status, "settled")
        self.assertIsNone(intent.fulfilled_at)
        self.assertFalse(
            EconomyAssetDelivery.objects.filter(
                payment_intent=intent,
            ).exists()
        )


class EconomyAssetRecoveryIdentityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="economy-recovery-user",
            password="test-password",
        )

        self.founder = FounderAccount.objects.create(
            handle="eco3",
            current_account=self.user,
            owner_root=self.user,
            status=FounderAccount.STATUS_OWNED,
        )

        self.asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Eco3Fanz",
            symbol="ECO3FANZ",
            status=EconomyAsset.STATUS_ACTIVE,
        )

    def create_intent(self, invoice_id):
        return PaymentIntent.objects.create(
            user=self.user,
            purpose="economy_asset_purchase",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id=invoice_id,
            metadata={
                "economy_asset_id": self.asset.pk,
                "recipient_address": "0x1234",
                "amount_base_units": 1_000_000,
            },
            paid_at=timezone.now(),
        )

    def test_deliveries_receive_unique_submission_keys(self):
        first_intent = self.create_intent("recovery-invoice-1")
        second_intent = self.create_intent("recovery-invoice-2")

        fulfill_payment_intent(first_intent.pk)
        fulfill_payment_intent(second_intent.pk)

        first = EconomyAssetDelivery.objects.get(
            payment_intent=first_intent
        )
        second = EconomyAssetDelivery.objects.get(
            payment_intent=second_intent
        )

        self.assertIsNotNone(first.submission_key)
        self.assertIsNotNone(second.submission_key)
        self.assertNotEqual(
            first.submission_key,
            second.submission_key,
        )

    def test_retry_preserves_submission_key(self):
        intent = self.create_intent("recovery-retry-invoice")

        fulfill_payment_intent(intent.pk)

        delivery = EconomyAssetDelivery.objects.get(
            payment_intent=intent
        )
        original_submission_key = delivery.submission_key

        fulfill_payment_intent(intent.pk)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.submission_key,
            original_submission_key,
        )

        self.assertEqual(
            EconomyAssetDelivery.objects.filter(
                payment_intent=intent
            ).count(),
            1,
        )

    def test_sender_address_is_optional(self):
        intent = self.create_intent("recovery-sender-invoice")

        fulfill_payment_intent(intent.pk)

        delivery = EconomyAssetDelivery.objects.get(
            payment_intent=intent
        )

        self.assertIsNone(delivery.sender_address)
