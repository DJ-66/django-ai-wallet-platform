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
from django.test import TestCase

from .models import (
    BidWallet,
    CreditPackage,
    CreditPurchase,
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
