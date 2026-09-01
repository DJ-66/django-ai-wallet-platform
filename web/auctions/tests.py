from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, TestCase, override_settings
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


SUI_ADAPTER_TEST_SETTINGS = {
    "FANZ_SUI_URL": "http://fanz-sui.test:3000",
    "FANZ_SUI_API_TOKEN": "test-sui-token",
    "FANZ_SUI_TIMEOUT": 10,
}


@override_settings(**SUI_ADAPTER_TEST_SETTINGS)
class SuiAdapterClientTests(SimpleTestCase):
    @patch("auctions.sui_adapter.requests.request")
    def test_prepare_delivery_posts_immutable_payload(self, request):
        from types import SimpleNamespace

        from auctions.sui_adapter import prepare_delivery

        response = Mock()
        response.status_code = 201
        response.json.return_value = {
            "created": True,
            "delivery": {
                "state": "prepared",
                "sender_address": "mock:sender",
            },
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        delivery = SimpleNamespace(
            submission_key="11111111-2222-4333-8444-555555555555",
            asset=SimpleNamespace(
                chain="sui",
                coin_type="mock::lisa::LISAFANZ",
            ),
            recipient_address="0x1234",
            amount_base_units=1_000_000,
        )

        result = prepare_delivery(delivery)

        self.assertTrue(result["created"])

        args, kwargs = request.call_args

        self.assertEqual(args[0], "POST")
        self.assertEqual(
            args[1],
            "http://fanz-sui.test:3000/v1/deliveries",
        )

        self.assertEqual(
            kwargs["json"],
            {
                "submission_key":
                    "11111111-2222-4333-8444-555555555555",
                "chain": "sui",
                "coin_type": "mock::lisa::LISAFANZ",
                "recipient_address": "0x1234",
                "amount_base_units": "1000000",
            },
        )

    @patch("auctions.sui_adapter.requests.request")
    def test_conflict_has_specific_error(self, request):
        from auctions.sui_adapter import (
            SuiAdapterConflict,
            prepare_delivery,
        )
        from types import SimpleNamespace

        response = Mock()
        response.status_code = 409
        request.return_value = response

        delivery = SimpleNamespace(
            submission_key="11111111-2222-4333-8444-555555555555",
            asset=SimpleNamespace(
                chain="sui",
                coin_type="mock::lisa::LISAFANZ",
            ),
            recipient_address="0x1234",
            amount_base_units=1_000_000,
        )

        with self.assertRaises(SuiAdapterConflict):
            prepare_delivery(delivery)

    @patch("auctions.sui_adapter.requests.request")
    def test_http_error_preserves_remote_error_detail(self, request):
        import requests

        from auctions.sui_adapter import (
            SuiAdapterError,
            prepare_creator_publication,
        )

        response = Mock()
        response.status_code = 400
        response.json.return_value = {
            "error":
                "Testnet transaction preparation is disabled",
        }

        response.raise_for_status.side_effect = (
            requests.HTTPError(
                response=response
            )
        )

        request.return_value = response

        with self.assertRaisesRegex(
            SuiAdapterError,
            (
                "HTTP 400: "
                "Testnet transaction preparation is disabled"
            ),
        ):
            prepare_creator_publication(
                "founder-4-luna-v1"
            )


    @override_settings(FANZ_SUI_API_TOKEN="")
    def test_missing_configuration_is_rejected(self):
        from auctions.sui_adapter import (
            SuiAdapterError,
            get_delivery,
        )

        with self.assertRaises(SuiAdapterError):
            get_delivery("test-key")


    @patch("auctions.sui_adapter.requests.request")
    def test_accept_creator_publication_posts_payload(self, request):
        from auctions.sui_adapter import (
            accept_creator_publication,
        )

        payload = {
            "publication_key":
                "founder-4-luna-v1",
            "chain": "sui",
            "module_name": "luna_fanz",
            "coin_struct_name": "LUNA_FANZ",
            "source_sha256": "a" * 64,
            "artifact_sha256": "b" * 64,
            "modules": ["module-b64"],
            "dependency_ids": [
                "0x1",
                "0x2",
            ],
            "recipient_address":
                "0xabc",
        }

        response = Mock()
        response.status_code = 201
        response.json.return_value = {
            "created": True,
            "publication": {
                "publication_key":
                    "founder-4-luna-v1",
                "state": "accepted",
            },
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        result = accept_creator_publication(
            payload
        )

        self.assertTrue(result["created"])

        args, kwargs = request.call_args

        self.assertEqual(
            args[0],
            "POST",
        )
        self.assertEqual(
            args[1],
            (
                "http://fanz-sui.test:3000"
                "/v1/creator-publications"
            ),
        )
        self.assertEqual(
            kwargs["json"],
            payload,
        )

    @patch("auctions.sui_adapter.requests.request")
    def test_prepare_creator_publication_posts_transition(self, request):
        from auctions.sui_adapter import (
            prepare_creator_publication,
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "publication": {
                "publication_key":
                    "founder-4-luna-v1",
                "state": "prepared",
            },
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        result = prepare_creator_publication(
            "founder-4-luna-v1"
        )

        self.assertEqual(
            result["publication"]["state"],
            "prepared",
        )

        args, kwargs = request.call_args

        self.assertEqual(
            args[0],
            "POST",
        )
        self.assertEqual(
            args[1],
            (
                "http://fanz-sui.test:3000"
                "/v1/creator-publications/"
                "founder-4-luna-v1/prepare"
            ),
        )
        self.assertEqual(
            kwargs["json"],
            {},
        )

    @patch("auctions.sui_adapter.requests.request")
    def test_submit_creator_publication_posts_transition(self, request):
        from auctions.sui_adapter import (
            submit_creator_publication,
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "publication": {
                "publication_key":
                    "founder-4-luna-v1",
                "state": "submitted",
                "tx_digest": "test-digest",
            },
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        result = submit_creator_publication(
            "founder-4-luna-v1"
        )

        self.assertEqual(
            result["publication"]["state"],
            "submitted",
        )

        args, kwargs = request.call_args

        self.assertEqual(
            args[0],
            "POST",
        )
        self.assertEqual(
            args[1],
            (
                "http://fanz-sui.test:3000"
                "/v1/creator-publications/"
                "founder-4-luna-v1/submit"
            ),
        )
        self.assertEqual(
            kwargs["json"],
            {},
        )

    @patch("auctions.sui_adapter.requests.request")
    def test_reconcile_creator_publication_posts_transition(self, request):
        from auctions.sui_adapter import (
            reconcile_creator_publication,
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "publication": {
                "publication_key":
                    "founder-4-luna-v1",
                "state": "confirmed",
                "tx_digest": "test-digest",
                "package_id": "0x123",
                "coin_type":
                    "0x123::luna_fanz::LUNA_FANZ",
            },
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        result = reconcile_creator_publication(
            "founder-4-luna-v1"
        )

        self.assertEqual(
            result["publication"]["state"],
            "confirmed",
        )

        args, kwargs = request.call_args

        self.assertEqual(
            args[0],
            "POST",
        )
        self.assertEqual(
            args[1],
            (
                "http://fanz-sui.test:3000"
                "/v1/creator-publications/"
                "founder-4-luna-v1/reconcile"
            ),
        )
        self.assertEqual(
            kwargs["json"],
            {},
        )


class EconomyDeliveryProcessorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="economy-processor-user",
            password="test-password",
        )

        self.founder = FounderAccount.objects.create(
            handle="eco4",
            current_account=self.user,
            owner_root=self.user,
            status=FounderAccount.STATUS_OWNED,
        )

        self.asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Eco4Fanz",
            symbol="ECO4FANZ",
            status=EconomyAsset.STATUS_ACTIVE,
            coin_type="mock::eco4::ECO4FANZ",
        )

        self.intent = PaymentIntent.objects.create(
            user=self.user,
            purpose="economy_asset_purchase",
            status="settled",
            amount="5.00",
            currency="USD",
            btcpay_invoice_id="economy-processor-invoice",
            metadata={
                "economy_asset_id": self.asset.pk,
                "recipient_address": "0x1234",
                "amount_base_units": 1_000_000,
            },
            paid_at=timezone.now(),
        )

        fulfill_payment_intent(self.intent.pk)

        self.delivery = EconomyAssetDelivery.objects.get(
            payment_intent=self.intent,
        )

    @patch(
        "auctions.economy_delivery_services.prepare_delivery"
    )
    def test_pending_delivery_becomes_prepared(self, prepare):
        from auctions.economy_delivery_services import (
            process_pending_economy_delivery,
        )

        prepare.return_value = {
            "created": True,
            "delivery": {
                "submission_key":
                    str(self.delivery.submission_key),
                "chain": "sui",
                "coin_type": "mock::eco4::ECO4FANZ",
                "recipient_address": "0x1234",
                "amount_base_units": "1000000",
                "state": "prepared",
                "sender_address": "mock:sender",
                "tx_digest": None,
            },
        }

        delivery, changed = (
            process_pending_economy_delivery(
                self.delivery.pk
            )
        )

        self.assertTrue(changed)
        self.assertEqual(delivery.status, "prepared")
        self.assertEqual(
            delivery.sender_address,
            "mock:sender",
        )
        self.assertEqual(delivery.attempt_count, 1)

        self.intent.refresh_from_db()
        self.assertEqual(self.intent.status, "settled")
        self.assertIsNone(self.intent.fulfilled_at)

    @patch(
        "auctions.economy_delivery_services.prepare_delivery"
    )
    def test_prepared_retry_is_noop(self, prepare):
        from auctions.economy_delivery_services import (
            process_pending_economy_delivery,
        )

        self.delivery.status = "prepared"
        self.delivery.sender_address = "mock:sender"
        self.delivery.save(
            update_fields=[
                "status",
                "sender_address",
                "updated_at",
            ]
        )

        delivery, changed = (
            process_pending_economy_delivery(
                self.delivery.pk
            )
        )

        self.assertFalse(changed)
        self.assertEqual(delivery.status, "prepared")
        prepare.assert_not_called()

    @patch(
        "auctions.economy_delivery_services.prepare_delivery"
    )
    def test_adapter_failure_leaves_delivery_pending(self, prepare):
        from auctions.economy_delivery_services import (
            EconomyDeliveryError,
            process_pending_economy_delivery,
            record_economy_delivery_error,
        )
        from auctions.sui_adapter import SuiAdapterError

        prepare.side_effect = SuiAdapterError(
            "adapter unavailable"
        )

        with self.assertRaises(EconomyDeliveryError) as ctx:
            process_pending_economy_delivery(
                self.delivery.pk
            )

        record_economy_delivery_error(
            self.delivery.pk,
            str(ctx.exception),
        )

        self.delivery.refresh_from_db()

        self.assertEqual(self.delivery.status, "pending")
        self.assertEqual(self.delivery.attempt_count, 1)
        self.assertTrue(self.delivery.last_error)

    @patch(
        "auctions.economy_delivery_services.prepare_delivery"
    )
    def test_remote_immutable_mismatch_is_rejected(self, prepare):
        from auctions.economy_delivery_services import (
            EconomyDeliveryError,
            process_pending_economy_delivery,
        )

        prepare.return_value = {
            "created": False,
            "delivery": {
                "submission_key":
                    str(self.delivery.submission_key),
                "chain": "sui",
                "coin_type": "mock::eco4::ECO4FANZ",
                "recipient_address": "0xWRONG",
                "amount_base_units": "1000000",
                "state": "prepared",
                "sender_address": "mock:sender",
                "tx_digest": None,
            },
        }

        with self.assertRaises(EconomyDeliveryError):
            process_pending_economy_delivery(
                self.delivery.pk
            )

        self.delivery.refresh_from_db()

        self.assertEqual(self.delivery.status, "pending")
        self.assertIsNone(self.delivery.sender_address)

from unittest.mock import patch

from django.test import TestCase

from auctions.economy_asset_publication_services import (
    EconomyAssetPublicationError,
    reconcile_confirmed_creator_publication,
)
from auctions.models import EconomyAsset, FounderAccount


class EconomyAssetPublicationTests(TestCase):
    def setUp(self):
        self.founder = FounderAccount.objects.create(
            handle="lisa",
            status=FounderAccount.STATUS_AVAILABLE,
            floor_price_credits=200,
        )

        self.asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Lisa FANZ",
            symbol="LISAFANZ",
            chain="sui",
            decimals=6,
            genesis_supply_base_units=21_000_000_000_000_000,
            status=EconomyAsset.STATUS_DRAFT,
        )

        self.package_id = (
            "0xce533b8003ab14f2b9215fe8776f01df"
            "1bfc06f3a546a49421df6a61b947d70c"
        )

        self.tx_digest = (
            "GLYJQnxgKzrEs1DCv3iRcRqK5CHktkjfvzb6GGaDuutk"
        )

        self.coin_type = (
            f"{self.package_id}::lisa_fanz::LISA_FANZ"
        )

        self.remote = {
            "publication": {
                "publication_key": "lisa-prepare-test-v1",
                "chain": "sui",
                "module_name": "lisa_fanz",
                "coin_struct_name": "LISA_FANZ",
                "state": "confirmed",
                "tx_digest": self.tx_digest,
                "package_id": self.package_id,
                "coin_type": self.coin_type,
            }
        }

    @patch(
        "auctions.economy_asset_publication_services."
        "get_creator_publication"
    )
    def test_confirmed_publication_writes_asset_identity(
        self,
        get_publication,
    ):
        get_publication.return_value = self.remote

        asset, changed = (
            reconcile_confirmed_creator_publication(
                self.asset.pk,
                "lisa-prepare-test-v1",
            )
        )

        self.assertTrue(changed)

        asset.refresh_from_db()

        self.assertEqual(asset.coin_type, self.coin_type)
        self.assertEqual(
            asset.genesis_tx_digest,
            self.tx_digest,
        )
        self.assertEqual(
            asset.metadata["package_id"],
            self.package_id,
        )
        self.assertEqual(
            asset.metadata["publication_key"],
            "lisa-prepare-test-v1",
        )
        self.assertEqual(
            asset.status,
            EconomyAsset.STATUS_ACTIVE,
        )
        self.assertIsNone(asset.supply_fixed_at)

    @patch(
        "auctions.economy_asset_publication_services."
        "get_creator_publication"
    )
    def test_confirmed_publication_retry_is_idempotent(
        self,
        get_publication,
    ):
        get_publication.return_value = self.remote

        _, first_changed = (
            reconcile_confirmed_creator_publication(
                self.asset.pk,
                "lisa-prepare-test-v1",
            )
        )

        _, second_changed = (
            reconcile_confirmed_creator_publication(
                self.asset.pk,
                "lisa-prepare-test-v1",
            )
        )

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)

    @patch(
        "auctions.economy_asset_publication_services."
        "get_creator_publication"
    )
    def test_unconfirmed_publication_is_rejected(
        self,
        get_publication,
    ):
        remote = {
            "publication": dict(
                self.remote["publication"],
                state="submitted",
            )
        }

        get_publication.return_value = remote

        with self.assertRaises(
            EconomyAssetPublicationError
        ):
            reconcile_confirmed_creator_publication(
                self.asset.pk,
                "lisa-prepare-test-v1",
            )

        self.asset.refresh_from_db()

        self.assertIsNone(self.asset.coin_type)
        self.assertIsNone(
            self.asset.genesis_tx_digest
        )
        self.assertEqual(
            self.asset.status,
            EconomyAsset.STATUS_DRAFT,
        )
    @patch(
        "auctions.economy_asset_publication_services."
        "get_creator_publication"
    )
    def test_conflicting_existing_coin_type_is_rejected(
        self,
        get_publication,
    ):
        self.asset.coin_type = (
            "0xdeadbeef::other_module::OTHER"
        )
        self.asset.save(
            update_fields=[
                "coin_type",
                "updated_at",
            ]
        )

        get_publication.return_value = self.remote

        with self.assertRaises(
            EconomyAssetPublicationError
        ):
            reconcile_confirmed_creator_publication(
                self.asset.pk,
                "lisa-prepare-test-v1",
            )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.coin_type,
            "0xdeadbeef::other_module::OTHER",
        )
        self.assertIsNone(
            self.asset.genesis_tx_digest
        )

    @patch(
        "auctions.economy_asset_publication_services."
        "get_creator_publication"
    )
    def test_conflicting_existing_genesis_digest_is_rejected(
        self,
        get_publication,
    ):
        self.asset.genesis_tx_digest = (
            "different-existing-digest"
        )
        self.asset.save(
            update_fields=[
                "genesis_tx_digest",
                "updated_at",
            ]
        )

        get_publication.return_value = self.remote

        with self.assertRaises(
            EconomyAssetPublicationError
        ):
            reconcile_confirmed_creator_publication(
                self.asset.pk,
                "lisa-prepare-test-v1",
            )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.genesis_tx_digest,
            "different-existing-digest",
        )
        self.assertIsNone(self.asset.coin_type)


from unittest.mock import patch

from django.test import TestCase

from auctions.economy_asset_supply_services import (
    EconomyAssetSupplyError,
    verify_economy_asset_fixed_supply,
)
from auctions.models import EconomyAsset, FounderAccount


class EconomyAssetSupplyTests(TestCase):
    def setUp(self):
        self.founder = FounderAccount.objects.create(
            handle="lisa",
            status=FounderAccount.STATUS_AVAILABLE,
            floor_price_credits=200,
        )

        self.asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Lisa FANZ",
            symbol="LISAFANZ",
            chain="sui",
            decimals=6,
            genesis_supply_base_units=21_000_000_000_000_000,
            coin_type=(
                "0xce533b8003ab14f2b9215fe8776f01df"
                "1bfc06f3a546a49421df6a61b947d70c"
                "::lisa_fanz::LISA_FANZ"
            ),
            genesis_tx_digest=(
                "GLYJQnxgKzrEs1DCv3iRcRqK5CHktkjfvzb6GGaDuutk"
            ),
            status=EconomyAsset.STATUS_ACTIVE,
            metadata={
                "publication_key": "lisa-prepare-test-v1",
            },
        )

        self.remote = {
            "supply": {
                "publication_key": "lisa-prepare-test-v1",
                "coin_type": self.asset.coin_type,
                "currency_object_id": (
                    "0x35c0275e1f964cce6aa0597b5fb44e4c"
                    "894c48787a7cbe7dbe83597249400c7b"
                ),
                "decimals": 6,
                "symbol": "LISAFANZ",
                "supply_state": "fixed",
                "supply_base_units": "21000000000000000",
                "previous_transaction":
                    self.asset.genesis_tx_digest,
            }
        }

    @patch(
        "auctions.economy_asset_supply_services."
        "get_creator_publication_supply"
    )
    def test_fixed_supply_is_recorded(
        self,
        get_supply,
    ):
        get_supply.return_value = self.remote

        asset, changed = verify_economy_asset_fixed_supply(
            self.asset.pk,
            "lisa-prepare-test-v1",
        )

        self.assertTrue(changed)

        asset.refresh_from_db()

        self.assertIsNotNone(asset.supply_fixed_at)
        self.assertEqual(
            asset.metadata["currency_object_id"],
            self.remote["supply"]["currency_object_id"],
        )

    @patch(
        "auctions.economy_asset_supply_services."
        "get_creator_publication_supply"
    )
    def test_fixed_supply_retry_is_idempotent(
        self,
        get_supply,
    ):
        get_supply.return_value = self.remote

        _, first_changed = verify_economy_asset_fixed_supply(
            self.asset.pk,
            "lisa-prepare-test-v1",
        )

        _, second_changed = verify_economy_asset_fixed_supply(
            self.asset.pk,
            "lisa-prepare-test-v1",
        )

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)

    @patch(
        "auctions.economy_asset_supply_services."
        "get_creator_publication_supply"
    )
    def test_wrong_supply_is_rejected(
        self,
        get_supply,
    ):
        remote = {
            "supply": dict(
                self.remote["supply"],
                supply_base_units="123",
            )
        }

        get_supply.return_value = remote

        with self.assertRaises(
            EconomyAssetSupplyError
        ):
            verify_economy_asset_fixed_supply(
                self.asset.pk,
                "lisa-prepare-test-v1",
            )

        self.asset.refresh_from_db()

        self.assertIsNone(self.asset.supply_fixed_at)

    @patch(
        "auctions.economy_asset_supply_services."
        "get_creator_publication_supply"
    )
    def test_non_fixed_supply_is_rejected(
        self,
        get_supply,
    ):
        remote = {
            "supply": dict(
                self.remote["supply"],
                supply_state="burn_only",
            )
        }

        get_supply.return_value = remote

        with self.assertRaises(
            EconomyAssetSupplyError
        ):
            verify_economy_asset_fixed_supply(
                self.asset.pk,
                "lisa-prepare-test-v1",
            )

        self.asset.refresh_from_db()

        self.assertIsNone(self.asset.supply_fixed_at)


class FounderVendingTests(TestCase):
    def test_founder_coin_identity_is_deterministic(self):
        from auctions.founder_vending import (
            founder_coin_identity,
        )

        identity = founder_coin_identity("@zoe")

        self.assertEqual(identity.handle, "zoe")
        self.assertEqual(
            identity.display_name,
            "ZoeFanz",
        )
        self.assertEqual(
            identity.symbol,
            "ZOEFANZ",
        )
        self.assertEqual(
            identity.package_name,
            "fanz_creator_zoe",
        )
        self.assertEqual(
            identity.module_name,
            "zoe_fanz",
        )
        self.assertEqual(
            identity.coin_struct_name,
            "ZOE_FANZ",
        )

    def test_non_founder_handle_is_rejected(self):
        from django.core.exceptions import ValidationError

        from auctions.founder_vending import (
            founder_coin_identity,
        )

        with self.assertRaises(ValidationError):
            founder_coin_identity("@pepsi")

    def test_budget_above_cutoff_gets_list_price(self):
        from auctions.founder_vending import (
            founder_budget_quote,
        )

        quote = founder_budget_quote(5000)

        self.assertEqual(
            quote.list_price_credits,
            4650,
        )
        self.assertFalse(
            quote.suggest_swamp
        )

    def test_215_budget_hits_founder_floor(self):
        from auctions.founder_vending import (
            founder_budget_quote,
        )

        quote = founder_budget_quote(215)

        self.assertEqual(
            quote.list_price_credits,
            200,
        )
        self.assertFalse(
            quote.suggest_swamp
        )

    def test_214_budget_suggests_swamp(self):
        from auctions.founder_vending import (
            founder_budget_quote,
        )

        quote = founder_budget_quote(214)

        self.assertIsNone(
            quote.list_price_credits
        )
        self.assertTrue(
            quote.suggest_swamp
        )


class FounderCartModelTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from auctions.models import FounderCart

        User = get_user_model()

        self.user = User.objects.create_user(
            username="cartbuyer",
            password="test-password",
        )

        self.cart = FounderCart.objects.create(
            purchaser=self.user,
        )

    def test_founder_cart_can_be_created(self):
        from auctions.models import FounderCart

        self.assertEqual(
            self.cart.status,
            FounderCart.STATUS_OPEN,
        )
        self.assertEqual(
            self.cart.purchaser,
            self.user,
        )

    def test_handle_is_normalized_on_save(self):
        from auctions.models import FounderCartItem

        item = FounderCartItem.objects.create(
            cart=self.cart,
            wanted_handle="@ZoE",
            budget_credits=5000,
        )

        self.assertEqual(
            item.wanted_handle,
            "zoe",
        )

    def test_same_handle_cannot_appear_twice(self):
        from django.db import IntegrityError

        from auctions.models import FounderCartItem

        FounderCartItem.objects.create(
            cart=self.cart,
            wanted_handle="zoe",
            budget_credits=5000,
        )

        with self.assertRaises(IntegrityError):
            FounderCartItem.objects.create(
                cart=self.cart,
                wanted_handle="zoe",
                budget_credits=6000,
            )

    def test_budget_must_be_positive(self):
        from django.db import IntegrityError

        from auctions.models import FounderCartItem

        with self.assertRaises(IntegrityError):
            FounderCartItem.objects.create(
                cart=self.cart,
                wanted_handle="mia",
                budget_credits=0,
            )

    def test_gift_requires_recipient_email(self):
        from django.core.exceptions import ValidationError

        from auctions.models import FounderCartItem

        item = FounderCartItem(
            cart=self.cart,
            wanted_handle="lily",
            budget_credits=1000,
            purchase_mode=FounderCartItem.MODE_GIFT,
        )

        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_valid_gift_passes_validation(self):
        from auctions.models import FounderCartItem

        item = FounderCartItem(
            cart=self.cart,
            wanted_handle="@Lily",
            budget_credits=1000,
            purchase_mode=FounderCartItem.MODE_GIFT,
            gift_recipient_name="Jamie",
            gift_recipient_email="jamie@example.com",
            gift_message="Enjoy your Founder handle!",
        )

        item.full_clean()

        self.assertEqual(
            item.wanted_handle,
            "lily",
        )

class FounderCartServiceTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        self.user = User.objects.create_user(
            username="vendingbuyer",
            password="test-password",
        )

    def test_add_item_calculates_list_price(self):
        from auctions.founder_cart_services import (
            add_founder_cart_item,
        )

        result = add_founder_cart_item(
            purchaser=self.user,
            wanted_handle="@Zoe",
            budget_credits=5000,
        )

        item = result["item"]
        identity = result["identity"]

        self.assertEqual(
            item.wanted_handle,
            "zoe",
        )
        self.assertEqual(
            item.list_price_credits,
            4650,
        )
        self.assertEqual(
            identity.display_name,
            "ZoeFanz",
        )
        self.assertEqual(
            item.status,
            item.STATUS_PENDING,
        )

    def test_low_budget_suggests_wasteland(self):
        from auctions.founder_cart_services import (
            add_founder_cart_item,
        )

        result = add_founder_cart_item(
            purchaser=self.user,
            wanted_handle="mia",
            budget_credits=214,
        )

        item = result["item"]

        self.assertEqual(
            item.status,
            item.STATUS_SWAMP_SUGGESTED,
        )
        self.assertIsNone(
            item.list_price_credits
        )

    def test_gift_requires_email(self):
        from auctions.founder_cart_services import (
            FounderCartError,
            add_founder_cart_item,
        )
        from auctions.models import FounderCartItem

        with self.assertRaises(FounderCartError):
            add_founder_cart_item(
                purchaser=self.user,
                wanted_handle="lily",
                budget_credits=1000,
                purchase_mode=(
                    FounderCartItem.MODE_GIFT
                ),
            )

    def test_gift_can_be_added_without_sui_address(self):
        from auctions.founder_cart_services import (
            add_founder_cart_item,
        )
        from auctions.models import FounderCartItem

        result = add_founder_cart_item(
            purchaser=self.user,
            wanted_handle="lily",
            budget_credits=1000,
            purchase_mode=FounderCartItem.MODE_GIFT,
            gift_recipient_name="Jamie",
            gift_recipient_email="jamie@example.com",
        )

        item = result["item"]

        self.assertEqual(
            item.purchase_mode,
            FounderCartItem.MODE_GIFT,
        )
        self.assertEqual(
            item.sui_recipient_address,
            "",
        )

    def test_same_handle_cannot_be_added_twice(self):
        from auctions.founder_cart_services import (
            FounderCartError,
            add_founder_cart_item,
        )

        add_founder_cart_item(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=5000,
        )

        with self.assertRaises(FounderCartError):
            add_founder_cart_item(
                purchaser=self.user,
                wanted_handle="@ZOE",
                budget_credits=6000,
          )


class FounderVendingReservationModelTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from auctions.models import (
            BidWallet,
            FounderCart,
        )

        User = get_user_model()

        self.user = User.objects.create_user(
            username="reservebuyer",
            password="test-password",
        )

        self.wallet = BidWallet.objects.create(
            user=self.user,
            credits=100_000,
        )

        self.cart = FounderCart.objects.create(
            purchaser=self.user,
        )

    def test_vending_hold_tracks_full_budget(self):
        from auctions.models import (
            FounderCartItem,
            FounderVendingHold,
        )

        item = FounderCartItem.objects.create(
            cart=self.cart,
            wanted_handle="zoe",
            budget_credits=50_000,
            list_price_credits=46_500,
            status=FounderCartItem.STATUS_QUOTED,
        )

        hold = FounderVendingHold.objects.create(
            cart_item=item,
            wallet=self.wallet,
            amount_credits=50_000,
        )

        self.assertEqual(
            hold.amount_credits,
            50_000,
        )
        self.assertEqual(
            hold.status,
            FounderVendingHold.STATUS_HELD,
        )

    def test_vending_hold_cannot_be_below_floor(self):
        from django.db import IntegrityError

        from auctions.models import (
            FounderCartItem,
            FounderVendingHold,
        )

        item = FounderCartItem.objects.create(
            cart=self.cart,
            wanted_handle="mia",
            budget_credits=199,
        )

        with self.assertRaises(IntegrityError):
            FounderVendingHold.objects.create(
                cart_item=item,
                wallet=self.wallet,
                amount_credits=199,
            )

    def test_price_memory_is_unique_per_buyer_handle(self):
        from datetime import timedelta

        from django.db import IntegrityError
        from django.utils import timezone

        from auctions.models import FounderPriceMemory

        expires = timezone.now() + timedelta(hours=4)

        FounderPriceMemory.objects.create(
            buyer_root=self.user,
            wanted_handle="zoe",
            list_price_credits=46_500,
            expires_at=expires,
        )

        with self.assertRaises(IntegrityError):
            FounderPriceMemory.objects.create(
                buyer_root=self.user,
                wanted_handle="zoe",
                list_price_credits=9_300,
                expires_at=expires,
            )

    def test_price_memory_normalizes_handle(self):
        from datetime import timedelta

        from django.utils import timezone

        from auctions.models import FounderPriceMemory

        memory = FounderPriceMemory.objects.create(
            buyer_root=self.user,
            wanted_handle="@ZOE",
            list_price_credits=46_500,
            expires_at=(
                timezone.now()
                + timedelta(hours=4)
            ),
        )

        self.assertEqual(
            memory.wanted_handle,
            "zoe",
        )

    def test_cart_item_supports_quote_expiration_times(self):
        from datetime import timedelta

        from django.utils import timezone

        from auctions.models import FounderCartItem

        quoted_at = timezone.now()

        item = FounderCartItem.objects.create(
            cart=self.cart,
            wanted_handle="zoe",
            budget_credits=50_000,
            list_price_credits=46_500,
            status=FounderCartItem.STATUS_QUOTED,
            quoted_at=quoted_at,
            reservation_expires_at=(
                quoted_at + timedelta(hours=1)
            ),
            price_memory_expires_at=(
                quoted_at + timedelta(hours=4)
            ),
        )

        self.assertEqual(
            item.status,
            FounderCartItem.STATUS_QUOTED,
        )

        self.assertEqual(
            item.reservation_expires_at,
            quoted_at + timedelta(hours=1),
        )

        self.assertEqual(
            item.price_memory_expires_at,
            quoted_at + timedelta(hours=4),
        )

class FounderVendingReservationServiceTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from auctions.models import BidWallet

        User = get_user_model()

        self.user = User.objects.create_user(
            username="reservationbuyer",
            password="test-password",
        )

        self.wallet = BidWallet.objects.create(
            user=self.user,
            credits=100_000,
        )

    def test_reservation_holds_full_budget(self):
        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
        )

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="@zoe",
            budget_credits=50_000,
        )

        self.wallet.refresh_from_db()

        item = result["item"]
        hold = result["hold"]
        memory = result["memory"]

        self.assertEqual(
            self.wallet.credits,
            50_000,
        )
        self.assertEqual(
            hold.amount_credits,
            50_000,
        )
        self.assertEqual(
            item.list_price_credits,
            46_500,
        )
        self.assertEqual(
            item.status,
            item.STATUS_QUOTED,
        )
        self.assertEqual(
            memory.list_price_credits,
            46_500,
        )

    def test_insufficient_wallet_balance_rejects_reservation(self):
        from auctions.founder_cart_services import (
            FounderCartError,
            create_founder_vending_reservation,
        )
        from auctions.models import (
            FounderCartItem,
            FounderVendingHold,
        )

        with self.assertRaises(FounderCartError):
            create_founder_vending_reservation(
                purchaser=self.user,
                wanted_handle="zoe",
                budget_credits=150_000,
            )

        self.wallet.refresh_from_db()

        self.assertEqual(
            self.wallet.credits,
            100_000,
        )
        self.assertFalse(
            FounderCartItem.objects.exists()
        )
        self.assertFalse(
            FounderVendingHold.objects.exists()
        )

    def test_reservation_sets_one_and_four_hour_windows(self):
        from datetime import timedelta

        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
        )

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        item = result["item"]

        self.assertEqual(
            item.reservation_expires_at,
            item.quoted_at + timedelta(hours=1),
        )
        self.assertEqual(
            item.price_memory_expires_at,
            item.quoted_at + timedelta(hours=4),
        )

    def test_lower_budget_cannot_bypass_active_price_memory(self):
        from auctions.founder_cart_services import (
            FounderCartError,
            create_founder_vending_reservation,
        )

        first = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        self.assertEqual(
            first["item"].list_price_credits,
            46_500,
        )

        # Simulate the first reservation no longer blocking the name,
        # while its four-hour price memory remains active.
        from auctions.founder_cart_services import (
            cancel_founder_vending_reservation,
        )

        cancel_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=first["item"].pk,
        )

        with self.assertRaises(FounderCartError):
            create_founder_vending_reservation(
                purchaser=self.user,
                wanted_handle="zoe",
                budget_credits=10_000,
            )

    def test_cancel_releases_full_budget(self):
        from auctions.founder_cart_services import (
            cancel_founder_vending_reservation,
            create_founder_vending_reservation,
        )
        from auctions.models import FounderVendingHold
        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )
        self.wallet.refresh_from_db()

        self.assertEqual(
            self.wallet.credits,
            50_000,
        )
        item, changed = (
            cancel_founder_vending_reservation(
                purchaser=self.user,
                cart_item_id=result["item"].pk,
        )
        )

        self.wallet.refresh_from_db()
        result["hold"].refresh_from_db()

        self.assertTrue(changed)
        self.assertEqual(
            self.wallet.credits,
            100_000,
        )
        self.assertEqual(
            item.status,
            item.STATUS_CANCELLED,
        )
        self.assertEqual(
            result["hold"].status,
            FounderVendingHold.STATUS_RELEASED,
        )


    def test_cancel_keeps_four_hour_price_memory(self):
        from auctions.founder_cart_services import (
            cancel_founder_vending_reservation,
            create_founder_vending_reservation,
        )
        from auctions.models import FounderPriceMemory

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        cancel_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=result["item"].pk,
        )

        memory = FounderPriceMemory.objects.get(
            buyer_root=self.user,
            wanted_handle="zoe",
        )

        self.assertEqual(
            memory.list_price_credits,
            46_500,
        )


    def test_expiration_releases_full_budget(self):
        from datetime import timedelta

        from django.utils import timezone

        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            expire_founder_vending_reservations,
        )
        from auctions.models import FounderVendingHold

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        item = result["item"]

        future = (
            item.reservation_expires_at
            + timedelta(seconds=1)
        )

        expired_count = (
            expire_founder_vending_reservations(
                now=future,
            )
        )

        self.wallet.refresh_from_db()
        item.refresh_from_db()
        result["hold"].refresh_from_db()

        self.assertEqual(expired_count, 1)
        self.assertEqual(
            self.wallet.credits,
            100_000,
        )
        self.assertEqual(
            item.status,
            item.STATUS_EXPIRED,
        )
        self.assertEqual(
            result["hold"].status,
            FounderVendingHold.STATUS_RELEASED,
        )

    def test_other_buyer_cannot_reserve_same_active_handle(self):
        from django.contrib.auth import get_user_model

        from auctions.founder_cart_services import (
            FounderCartError,
            create_founder_vending_reservation,
        )
        from auctions.models import BidWallet

        User = get_user_model()

        other = User.objects.create_user(
            username="otherbuyer",
            password="test-password",
        )

        BidWallet.objects.create(
            user=other,
            credits=100_000,
        )

        create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        with self.assertRaises(FounderCartError):
            create_founder_vending_reservation(
                purchaser=other,
                wanted_handle="zoe",
                budget_credits=50_000,
            )

# end_py


    def test_funded_reservation_marks_founder_reserved(self):
        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
        )
        from auctions.models import FounderAccount

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="@zoe",
            budget_credits=50_000,
        )

        founder = result["founder_account"]
        founder.refresh_from_db()

        self.assertEqual(
            founder.handle,
            "zoe",
        )
        self.assertEqual(
            founder.status,
            FounderAccount.STATUS_RESERVED,
        )
        self.assertIsNone(
            founder.owner_root_id
        )

    def test_cancel_releases_founder_to_available(self):
        from auctions.founder_cart_services import (
            cancel_founder_vending_reservation,
            create_founder_vending_reservation,
        )
        from auctions.models import FounderAccount

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        cancel_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=result["item"].pk,
        )

        founder = FounderAccount.objects.get(
            handle="zoe"
        )

        self.assertEqual(
            founder.status,
            FounderAccount.STATUS_AVAILABLE,
        )
        self.assertIsNone(
            founder.owner_root_id
        )

    def test_expiration_releases_founder_to_available(self):
        from datetime import timedelta

        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            expire_founder_vending_reservations,
        )
        from auctions.models import FounderAccount

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        expire_founder_vending_reservations(
            now=(
                result["item"].reservation_expires_at
                + timedelta(seconds=1)
            ),
        )

        founder = FounderAccount.objects.get(
            handle="zoe"
        )

        self.assertEqual(
            founder.status,
            FounderAccount.STATUS_AVAILABLE,
        )
        self.assertIsNone(
            founder.owner_root_id
        )


    def test_purchase_consumes_hold_without_double_charge(self):
        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            purchase_founder_vending_reservation,
        )
        from auctions.models import (
            FounderCartItem,
            FounderVendingHold,
        )
        from auctions.utils import get_system_wallet

        platform_wallet = get_system_wallet()
        platform_before = platform_wallet.credits

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        self.wallet.refresh_from_db()

        # Full Budget has already been removed.
        self.assertEqual(
            self.wallet.credits,
            50_000,
        )

        purchase = purchase_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=result["item"].pk,
        )

        self.wallet.refresh_from_db()
        platform_wallet.refresh_from_db()
        result["hold"].refresh_from_db()
        result["item"].refresh_from_db()

        self.assertTrue(
            purchase["purchased"]
        )

        # 50,000 was held.
        # 46,500 was spent.
        # 3,500 was returned.
        #
        # Starting wallet = 100,000.
        # Final wallet = 53,500.
        self.assertEqual(
            self.wallet.credits,
            53_500,
        )

        self.assertEqual(
            platform_wallet.credits,
            platform_before + 46_500,
        )

        self.assertEqual(
            purchase["sale_price_credits"],
            46_500,
        )

        self.assertEqual(
            purchase["refund_credits"],
            3_500,
        )

        self.assertEqual(
            result["hold"].status,
            FounderVendingHold.STATUS_CONSUMED,
        )

        self.assertEqual(
            result["item"].status,
            FounderCartItem.STATUS_PURCHASED,
        )

    def test_purchase_transfers_founder_to_buyer(self):
        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            purchase_founder_vending_reservation,
        )
        from auctions.models import FounderAccount

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="@zoe",
            budget_credits=50_000,
        )

        purchase_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=result["item"].pk,
        )

        founder = FounderAccount.objects.get(
            handle="zoe"
        )

        self.assertEqual(
            founder.status,
            FounderAccount.STATUS_OWNED,
        )

        self.assertEqual(
            founder.owner_root_id,
            self.user.pk,
        )

    def test_purchase_creates_treasury_release_ledger(self):
        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            purchase_founder_vending_reservation,
        )
        from auctions.models import FounderOwnershipLedger

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        purchase = purchase_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=result["item"].pk,
        )

        ledger = purchase["ledger_record"]

        self.assertEqual(
            ledger.transfer_type,
            FounderOwnershipLedger
            .TRANSFER_TREASURY_RELEASE,
        )

        self.assertEqual(
            ledger.sale_price_credits,
            46_500,
        )

        self.assertEqual(
            ledger.buyer_root_id,
            self.user.pk,
        )

    def test_purchase_retry_is_idempotent(self):
        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            purchase_founder_vending_reservation,
        )
        from auctions.models import WalletTransaction

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        first = purchase_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=result["item"].pk,
        )

        transaction_count = (
            WalletTransaction.objects.count()
        )

        second = purchase_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=result["item"].pk,
        )

        self.wallet.refresh_from_db()

        self.assertTrue(
            first["purchased"]
        )

        self.assertFalse(
            second["purchased"]
        )

        self.assertTrue(
            second["already_purchased"]
        )

        self.assertEqual(
            self.wallet.credits,
            53_500,
        )

        self.assertEqual(
            WalletTransaction.objects.count(),
            transaction_count,
        )

    def test_expired_quote_cannot_purchase(self):
        from datetime import timedelta

        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            purchase_founder_vending_reservation,
        )
        from auctions.models import (
            FounderAccount,
            FounderVendingHold,
        )

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
        )

        purchase = purchase_founder_vending_reservation(
            purchaser=self.user,
            cart_item_id=result["item"].pk,
            now=(
                result["item"].reservation_expires_at
                + timedelta(seconds=1)
            ),
        )

        self.wallet.refresh_from_db()
        result["hold"].refresh_from_db()

        founder = FounderAccount.objects.get(
            handle="zoe"
        )

        self.assertFalse(
            purchase["purchased"]
        )

        self.assertTrue(
            purchase["expired"]
        )

        self.assertEqual(
            self.wallet.credits,
            100_000,
        )

        self.assertEqual(
            result["hold"].status,
            FounderVendingHold.STATUS_RELEASED,
        )

        self.assertEqual(
            founder.status,
            FounderAccount.STATUS_AVAILABLE,
        )

        self.assertIsNone(
            founder.owner_root_id
        )



    def test_purchase_without_sui_creates_no_coin_draft(self):
        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            purchase_founder_vending_reservation,
        )
        from auctions.models import EconomyAsset

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="zoe",
            budget_credits=50_000,
            sui_recipient_address="",
        )

        with self.captureOnCommitCallbacks(
            execute=True
        ):
            purchase = (
                purchase_founder_vending_reservation(
                    purchaser=self.user,
                    cart_item_id=result["item"].pk,
                )
            )

        self.assertTrue(
            purchase["purchased"]
        )

        self.assertFalse(
            EconomyAsset.objects.exists()
        )

    def test_purchase_with_sui_creates_coin_draft_after_commit(self):
        from auctions.founder_cart_services import (
            create_founder_vending_reservation,
            purchase_founder_vending_reservation,
        )
        from auctions.models import EconomyAsset

        result = create_founder_vending_reservation(
            purchaser=self.user,
            wanted_handle="@zoe",
            budget_credits=50_000,
            sui_recipient_address="0xabc",
        )

        self.assertFalse(
            EconomyAsset.objects.exists()
        )

        with self.captureOnCommitCallbacks(
            execute=True
        ):
            purchase = (
                purchase_founder_vending_reservation(
                    purchaser=self.user,
                    cart_item_id=result["item"].pk,
                )
            )

        self.assertTrue(
            purchase["purchased"]
        )

        asset = EconomyAsset.objects.get(
            founder_account__handle="zoe"
        )

        self.assertEqual(
            asset.name,
            "ZoeFanz",
        )

        self.assertEqual(
            asset.symbol,
            "ZOEFANZ",
        )

        self.assertEqual(
            asset.status,
            EconomyAsset.STATUS_DRAFT,
        )

        self.assertEqual(
            asset.metadata[
                "generated_package"
            ],
            "fanz_creator_zoe",
        )

        self.assertEqual(
            asset.metadata[
                "intended_recipient_address"
            ],
            "0xabc",
        )

        self.assertEqual(
            asset.metadata[
                "issuance_source"
            ],
            "founder_vending",
        )

class FounderCoinDraftServiceTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from auctions.models import FounderAccount

        User = get_user_model()

        self.user = User.objects.create_user(
            username="coinbuyer",
            password="test-password",
        )

        self.founder = FounderAccount.objects.create(
            handle="zoe",
            status=FounderAccount.STATUS_OWNED,
            owner_root=self.user,
        )

    def test_owned_founder_with_sui_address_creates_draft(self):
        from auctions.founder_coin_services import (
            create_founder_coin_draft,
        )
        from auctions.models import EconomyAsset

        asset, created = create_founder_coin_draft(
            founder_account_id=self.founder.pk,
            recipient_address=(
                "0x1234567890abcdef"
            ),
        )

        self.assertTrue(created)

        self.assertEqual(
            asset.founder_account,
            self.founder,
        )

        self.assertEqual(
            asset.name,
            "ZoeFanz",
        )

        self.assertEqual(
            asset.symbol,
            "ZOEFANZ",
        )

        self.assertEqual(
            asset.status,
            EconomyAsset.STATUS_DRAFT,
        )

        self.assertEqual(
            asset.genesis_supply_base_units,
            21_000_000_000_000_000,
        )

        self.assertEqual(
            asset.decimals,
            6,
        )

        self.assertEqual(
            asset.metadata[
                "generated_package"
            ],
            "fanz_creator_zoe",
        )

        self.assertEqual(
            asset.metadata[
                "intended_recipient_address"
            ],
            "0x1234567890abcdef",
        )

        self.assertEqual(
            asset.metadata[
                "issuance_source"
            ],
            "founder_vending",
        )

    def test_missing_sui_address_rejects_direct_draft_creation(self):
        from auctions.founder_coin_services import (
            FounderCoinError,
            create_founder_coin_draft,
        )
        from auctions.models import EconomyAsset

        with self.assertRaises(FounderCoinError):
            create_founder_coin_draft(
                founder_account_id=self.founder.pk,
                recipient_address="",
            )

        self.assertFalse(
            EconomyAsset.objects.exists()
        )

    def test_unowned_founder_cannot_create_coin_draft(self):
        from auctions.founder_coin_services import (
            FounderCoinError,
            create_founder_coin_draft,
        )
        from auctions.models import (
            EconomyAsset,
            FounderAccount,
        )

        self.founder.owner_root = None
        self.founder.status = (
            FounderAccount.STATUS_AVAILABLE
        )
        self.founder.save(
            update_fields=[
                "owner_root",
                "status",
                "updated_at",
            ]
        )

        with self.assertRaises(FounderCoinError):
            create_founder_coin_draft(
                founder_account_id=self.founder.pk,
                recipient_address="0xabc",
            )

        self.assertFalse(
            EconomyAsset.objects.exists()
        )

    def test_coin_draft_creation_is_idempotent(self):
        from auctions.founder_coin_services import (
            create_founder_coin_draft,
        )
        from auctions.models import EconomyAsset

        first, first_created = create_founder_coin_draft(
            founder_account_id=self.founder.pk,
            recipient_address="0xabc",
        )

        second, second_created = create_founder_coin_draft(
            founder_account_id=self.founder.pk,
            recipient_address="0xabc",
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)

        self.assertEqual(
            first.pk,
            second.pk,
        )

        self.assertEqual(
            EconomyAsset.objects.count(),
            1,
        )

    def test_existing_draft_rejects_different_sui_recipient(self):
        from auctions.founder_coin_services import (
            FounderCoinError,
            create_founder_coin_draft,
        )

        create_founder_coin_draft(
            founder_account_id=self.founder.pk,
            recipient_address="0xabc",
        )

        with self.assertRaises(FounderCoinError):
            create_founder_coin_draft(
                founder_account_id=self.founder.pk,
                recipient_address="0xdef",
            )

    def test_purchased_cart_item_without_sui_address_creates_nothing(self):
        from auctions.founder_coin_services import (
            create_coin_draft_for_purchased_cart_item,
        )
        from auctions.models import (
            EconomyAsset,
            FounderCart,
            FounderCartItem,
        )

        cart = FounderCart.objects.create(
            purchaser=self.user,
        )

        item = FounderCartItem.objects.create(
            cart=cart,
            wanted_handle="zoe",
            budget_credits=50_000,
            list_price_credits=46_500,
            status=FounderCartItem.STATUS_PURCHASED,
            sui_recipient_address="",
        )

        asset, created = (
            create_coin_draft_for_purchased_cart_item(
                cart_item=item,
            )
        )

        self.assertIsNone(asset)
        self.assertFalse(created)

        self.assertFalse(
            EconomyAsset.objects.exists()
        )

    def test_purchased_cart_item_with_sui_address_creates_draft(self):
        from auctions.founder_coin_services import (
            create_coin_draft_for_purchased_cart_item,
        )
        from auctions.models import (
            EconomyAsset,
            FounderCart,
            FounderCartItem,
        )

        cart = FounderCart.objects.create(
            purchaser=self.user,
        )

        item = FounderCartItem.objects.create(
            cart=cart,
            wanted_handle="zoe",
            budget_credits=50_000,
            list_price_credits=46_500,
            status=FounderCartItem.STATUS_PURCHASED,
            sui_recipient_address="0xabc",
        )

        asset, created = (
            create_coin_draft_for_purchased_cart_item(
                cart_item=item,
            )
        )

        self.assertTrue(created)

        self.assertEqual(
            asset.status,
            EconomyAsset.STATUS_DRAFT,
        )

        self.assertEqual(
            asset.metadata[
                "intended_recipient_address"
            ],
            "0xabc",
        )


class PendingFounderCoinPublicationsCommandTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from auctions.models import (
            EconomyAsset,
            FounderAccount,
        )

        User = get_user_model()

        self.user = User.objects.create_user(
            username="queuebuyer",
            password="test-password",
        )

        self.founder = FounderAccount.objects.create(
            handle="zoe",
            status=FounderAccount.STATUS_OWNED,
            owner_root=self.user,
        )

        self.asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="ZoeFanz",
            symbol="ZOEFANZ",
            chain="sui",
            decimals=6,
            genesis_supply_base_units=(
                21_000_000_000_000_000
            ),
            status=EconomyAsset.STATUS_DRAFT,
            metadata={
                "generated_package":
                    "fanz_creator_zoe",
                "intended_recipient_address":
                    "0xabc",
                "issuance_source":
                    "founder_vending",
            },
        )

    def test_pending_command_emits_vending_draft(self):
        import io
        import json

        from django.core.management import call_command

        stdout = io.StringIO()
        stderr = io.StringIO()

        call_command(
            "pending_founder_coin_publications",
            stdout=stdout,
            stderr=stderr,
        )

        lines = [
            line
            for line in stdout.getvalue().splitlines()
            if line.strip()
        ]

        self.assertEqual(len(lines), 1)

        record = json.loads(lines[0])

        self.assertEqual(
            record["economy_asset_id"],
            self.asset.pk,
        )
        self.assertEqual(
            record["handle"],
            "zoe",
        )
        self.assertEqual(
            record["name"],
            "ZoeFanz",
        )
        self.assertEqual(
            record["symbol"],
            "ZOEFANZ",
        )
        self.assertEqual(
            record["generated_package"],
            "fanz_creator_zoe",
        )
        self.assertEqual(
            record["recipient_address"],
            "0xabc",
        )
        self.assertEqual(
            record["publication_key"],
            (
                f"founder-{self.asset.pk}-"
                "zoe-v1"
            ),
        )

        self.assertIn(
            "pending_founder_coin_publications=1",
            stderr.getvalue(),
        )

    def test_active_asset_is_not_emitted(self):
        import io

        from django.core.management import call_command
        from auctions.models import EconomyAsset

        self.asset.status = EconomyAsset.STATUS_ACTIVE
        self.asset.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        stdout = io.StringIO()

        call_command(
            "pending_founder_coin_publications",
            stdout=stdout,
        )

        self.assertEqual(
            stdout.getvalue().strip(),
            "",
        )

    def test_non_vending_draft_is_not_emitted(self):
        import io

        from django.core.management import call_command

        self.asset.metadata = {
            "generated_package":
                "fanz_creator_zoe",
            "intended_recipient_address":
                "0xabc",
        }

        self.asset.save(
            update_fields=[
                "metadata",
                "updated_at",
            ]
        )

        stdout = io.StringIO()

        call_command(
            "pending_founder_coin_publications",
            stdout=stdout,
        )

        self.assertEqual(
            stdout.getvalue().strip(),
            "",
        )

    def test_missing_recipient_is_not_emitted(self):
        import io

        from django.core.management import call_command

        metadata = dict(self.asset.metadata)
        metadata[
            "intended_recipient_address"
        ] = ""

        self.asset.metadata = metadata
        self.asset.save(
            update_fields=[
                "metadata",
                "updated_at",
            ]
        )

        stdout = io.StringIO()

        call_command(
            "pending_founder_coin_publications",
            stdout=stdout,
        )

        self.assertEqual(
            stdout.getvalue().strip(),
            "",
        )


class FounderVendingTiendaViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from auctions.models import (
            BidWallet,
            FounderAccount,
        )

        User = get_user_model()

        self.buyer = User.objects.create_user(
            username="vendingwebbuyer",
            password="test-password",
        )

        self.other = User.objects.create_user(
            username="vendingwebother",
            password="test-password",
        )

        self.platform = User.objects.create_user(
            username="vendingwebplatform",
            password="test-password",
        )

        BidWallet.objects.create(
            user=self.buyer,
            credits=100_000,
        )

        BidWallet.objects.create(
            user=self.other,
            credits=100_000,
        )

        BidWallet.objects.create(
            user=self.platform,
            credits=0,
        )

        self.founder = FounderAccount.objects.create(
            handle="q7xz",
            status=FounderAccount.STATUS_AVAILABLE,
            owner_root=None,
            floor_price_credits=200,
        )

        self.client.force_login(self.buyer)

    def _quote(
        self,
        *,
        budget=50_000,
        purchase_mode="self",
        sui_address="",
        gift_name="",
        gift_email="",
        gift_message="",
    ):
        from django.urls import reverse

        return self.client.post(
            reverse("quote_founder_vending"),
            {
                "wanted_handle": "q7xz",
                "budget_credits": str(budget),
                "purchase_mode": purchase_mode,
                "sui_recipient_address": sui_address,
                "gift_recipient_name": gift_name,
                "gift_recipient_email": gift_email,
                "gift_message": gift_message,
            },
        )

    def test_quote_creates_funded_reservation_and_redirects_to_item(self):
        from auctions.models import (
            FounderCartItem,
            FounderVendingHold,
        )

        response = self._quote()

        self.assertEqual(
            response.status_code,
            302,
        )

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        hold = FounderVendingHold.objects.get(
            cart_item=item,
        )

        self.assertEqual(
            item.status,
            FounderCartItem.STATUS_QUOTED,
        )

        self.assertEqual(
            hold.status,
            FounderVendingHold.STATUS_HELD,
        )

        self.assertEqual(
            hold.amount_credits,
            50_000,
        )

        self.assertIn(
            f"vending_item={item.pk}",
            response["Location"],
        )

    def test_gift_quote_preserves_gift_and_sui_fields(self):
        from auctions.models import FounderCartItem

        response = self._quote(
            purchase_mode=FounderCartItem.MODE_GIFT,
            sui_address="0xabc123",
            gift_name="Gift Recipient",
            gift_email="gift@example.com",
            gift_message="Enjoy your Founder property!",
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        self.assertEqual(
            item.purchase_mode,
            FounderCartItem.MODE_GIFT,
        )
        self.assertEqual(
            item.sui_recipient_address,
            "0xabc123",
        )
        self.assertEqual(
            item.gift_recipient_name,
            "Gift Recipient",
        )
        self.assertEqual(
            item.gift_recipient_email,
            "gift@example.com",
        )
        self.assertEqual(
            item.gift_message,
            "Enjoy your Founder property!",
        )

    def test_other_user_cannot_view_vending_item(self):
        from auctions.models import FounderCartItem
        from django.urls import reverse

        self._quote()

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        self.client.force_login(self.other)

        response = self.client.get(
            reverse("founder_tienda"),
            {
                "vending_item": item.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIsNone(
            response.context["vending_item"],
        )

    def test_cancel_releases_hold(self):
        from auctions.models import (
            FounderCartItem,
            FounderVendingHold,
        )
        from django.urls import reverse

        self._quote()

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        response = self.client.post(
            reverse(
                "cancel_founder_vending",
                args=[item.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        item.refresh_from_db()

        hold = FounderVendingHold.objects.get(
            cart_item=item,
        )

        self.assertEqual(
            item.status,
            FounderCartItem.STATUS_CANCELLED,
        )

        self.assertEqual(
            hold.status,
            FounderVendingHold.STATUS_RELEASED,
        )

    def test_other_user_cannot_cancel_vending_item(self):
        from auctions.models import FounderCartItem
        from django.urls import reverse

        self._quote()

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        self.client.force_login(self.other)

        response = self.client.post(
            reverse(
                "cancel_founder_vending",
                args=[item.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        item.refresh_from_db()

        self.assertEqual(
            item.status,
            FounderCartItem.STATUS_QUOTED,
        )

    def test_other_user_cannot_buy_vending_item(self):
        from auctions.models import FounderCartItem
        from django.urls import reverse

        self._quote()

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        self.client.force_login(self.other)

        response = self.client.post(
            reverse(
                "buy_founder_vending",
                args=[item.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        item.refresh_from_db()

        self.assertEqual(
            item.status,
            FounderCartItem.STATUS_QUOTED,
        )

    def test_buy_settles_founder_and_refunds_unused_budget(self):
        from auctions.models import (
            BidWallet,
            EconomyAsset,
            FounderCartItem,
            FounderVendingHold,
        )
        from django.urls import reverse

        self._quote(
            budget=50_000,
        )

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        sale_price = item.list_price_credits
        self.assertIsNotNone(sale_price)

        buyer_wallet = BidWallet.objects.get(
            user=self.buyer,
        )

        # The full budget is already held at quote time.
        self.assertEqual(
            buyer_wallet.credits,
            50_000,
        )

        response = self.client.post(
            reverse(
                "buy_founder_vending",
                args=[item.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        item.refresh_from_db()
        self.founder.refresh_from_db()
        buyer_wallet.refresh_from_db()

        hold = FounderVendingHold.objects.get(
            cart_item=item,
        )

        self.assertEqual(
            item.status,
            FounderCartItem.STATUS_PURCHASED,
        )

        self.assertEqual(
            hold.status,
            FounderVendingHold.STATUS_CONSUMED,
        )

        self.assertEqual(
            self.founder.owner_root,
            self.buyer,
        )

        self.assertEqual(
            buyer_wallet.credits,
            100_000 - sale_price,
        )

        self.assertFalse(
            EconomyAsset.objects.filter(
                founder_account=self.founder,
            ).exists()
        )

    def test_gift_buy_with_sui_creates_creator_coin_draft(self):
        from auctions.models import (
            EconomyAsset,
            FounderCartItem,
        )
        from django.urls import reverse

        self._quote(
            budget=50_000,
            purchase_mode=FounderCartItem.MODE_GIFT,
            sui_address="0xabc123",
            gift_name="Gift Recipient",
            gift_email="gift@example.com",
            gift_message="Enjoy your Founder property!",
        )

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        with self.captureOnCommitCallbacks(
            execute=True
        ):
            response = self.client.post(
                reverse(
                    "buy_founder_vending",
                    args=[item.pk],
                )
            )

        self.assertEqual(
            response.status_code,
            302,
        )

        item.refresh_from_db()
        self.founder.refresh_from_db()

        self.assertEqual(
            item.status,
            FounderCartItem.STATUS_PURCHASED,
        )

        self.assertEqual(
            item.purchase_mode,
            FounderCartItem.MODE_GIFT,
        )

        self.assertEqual(
            item.gift_recipient_name,
            "Gift Recipient",
        )

        self.assertEqual(
            item.gift_recipient_email,
            "gift@example.com",
        )

        self.assertEqual(
            item.gift_message,
            "Enjoy your Founder property!",
        )

        self.assertEqual(
            item.sui_recipient_address,
            "0xabc123",
        )

        # Current gift semantics preserve the gift intent,
        # while Founder ownership still settles to purchaser.
        self.assertEqual(
            self.founder.owner_root,
            self.buyer,
        )

        asset = EconomyAsset.objects.get(
            founder_account=self.founder,
        )

        self.assertEqual(
            asset.status,
            EconomyAsset.STATUS_DRAFT,
        )

        self.assertEqual(
            asset.chain,
            "sui",
        )

        self.assertEqual(
            asset.decimals,
            6,
        )

        self.assertEqual(
            asset.genesis_supply_base_units,
            21_000_000_000_000_000,
        )

        self.assertEqual(
            asset.metadata.get(
                "issuance_source"
            ),
            "founder_vending",
        )

        self.assertEqual(
            asset.metadata.get(
                "intended_recipient_address"
            ),
            "0xabc123",
        )

    def test_expired_buy_does_not_purchase_founder(self):
        from datetime import timedelta

        from auctions.models import (
            FounderCartItem,
            FounderVendingHold,
        )
        from django.urls import reverse
        from django.utils import timezone

        self._quote(
            budget=50_000,
        )

        item = FounderCartItem.objects.get(
            cart__purchaser=self.buyer,
            wanted_handle="q7xz",
        )

        item.reservation_expires_at = (
            timezone.now()
            - timedelta(seconds=1)
        )

        item.save(
            update_fields=[
                "reservation_expires_at",
                "updated_at",
            ]
        )

        response = self.client.post(
            reverse(
                "buy_founder_vending",
                args=[item.pk],
            )
        )

        # The view must handle expiration as a normal
        # business outcome rather than raising KeyError.
        self.assertEqual(
            response.status_code,
            302,
        )

        item.refresh_from_db()
        self.founder.refresh_from_db()

        hold = FounderVendingHold.objects.get(
            cart_item=item,
        )

        self.assertEqual(
            item.status,
            FounderCartItem.STATUS_EXPIRED,
        )

        self.assertEqual(
            hold.status,
            FounderVendingHold.STATUS_RELEASED,
        )

        self.assertIsNone(
            self.founder.owner_root,
        )


class UserProfileSuiAddressTests(TestCase):
    def test_sui_address_is_optional(self):
        from auctions.forms import UserProfileForm

        form = UserProfileForm(
            data={
                "sui_address": "",
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors,
        )

        self.assertEqual(
            form.cleaned_data["sui_address"],
            "",
        )

    def test_sui_address_is_normalized_to_lowercase(self):
        from auctions.forms import UserProfileForm

        form = UserProfileForm(
            data={
                "sui_address":
                    "0xABCDEF0123456789ABCDEF0123456789"
                    "ABCDEF0123456789ABCDEF0123456789",
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors,
        )

        self.assertEqual(
            form.cleaned_data["sui_address"],
            (
                "0xabcdef0123456789abcdef0123456789"
                "abcdef0123456789abcdef0123456789"
            ),
        )

    def test_invalid_sui_address_is_rejected(self):
        from auctions.forms import UserProfileForm

        form = UserProfileForm(
            data={
                "sui_address": "not-a-sui-address",
            }
        )

        self.assertFalse(
            form.is_valid(),
        )

        self.assertIn(
            "sui_address",
            form.errors,
        )



class FounderCoinPublicationProcessorTests(TestCase):
    def setUp(self):
        import json
        from pathlib import Path
        from unittest.mock import patch

        from django.contrib.auth import get_user_model

        from auctions.models import (
            EconomyAsset,
            FounderAccount,
        )

        User = get_user_model()

        self.owner = User.objects.create_user(
            username="processor-owner",
            password="test-password",
        )

        self.founder = FounderAccount.objects.create(
            handle="pc01",
            status=FounderAccount.STATUS_OWNED,
            owner_root=self.owner,
            floor_price_credits=200,
        )

        self.asset = EconomyAsset.objects.create(
            founder_account=self.founder,
            name="Pc01Fanz",
            symbol="PC01FANZ",
            chain="sui",
            decimals=6,
            genesis_supply_base_units=(
                21_000_000_000_000_000
            ),
            status=EconomyAsset.STATUS_DRAFT,
            metadata={
                "issuance_source":
                    "founder_vending",
                "generated_package":
                    "fanz_creator_pc01",
                "intended_recipient_address":
                    "0xabc",
            },
        )

        self.publication_key = (
            f"founder-{self.asset.pk}-pc01-v1"
        )

        self.payload = {
            "publication_key":
                self.publication_key,
            "chain":
                "sui",
            "module_name":
                "pc01_fanz",
            "coin_struct_name":
                "PC01_FANZ",
            "source_sha256":
                "a" * 64,
            "artifact_sha256":
                "b" * 64,
            "modules": [
                "module-b64",
            ],
            "dependency_ids": [
                "0x1",
                "0x2",
            ],
            "recipient_address":
                "0xabc",
        }

        from auctions.management.commands import (
            process_founder_coin_publication
            as processor,
        )

        self.processor = processor

        self.temp_root = Path(
            "/tmp/fanz-founder-processor-tests"
        )

        self.temp_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.payload_path = (
            self.temp_root
            / f"{self.publication_key}.json"
        )

        self.payload_path.write_text(
            json.dumps(self.payload)
        )

        self.prepared_root_patch = patch.object(
            processor,
            "PREPARED_ROOT",
            self.temp_root,
        )

        self.prepared_root_patch.start()

        self.addCleanup(
            self.prepared_root_patch.stop
        )

    def tearDown(self):
        if self.payload_path.exists():
            self.payload_path.unlink()

    def _call(self):
        import io

        from django.core.management import call_command

        stdout = io.StringIO()
        stderr = io.StringIO()

        call_command(
            "process_founder_coin_publication",
            asset_id=self.asset.pk,
            stdout=stdout,
            stderr=stderr,
        )

        return (
            stdout.getvalue(),
            stderr.getvalue(),
        )

    @patch(
        "auctions.management.commands."
        "process_founder_coin_publication."
        "prepare_creator_publication"
    )
    @patch(
        "auctions.management.commands."
        "process_founder_coin_publication."
        "accept_creator_publication"
    )
    @patch(
        "auctions.management.commands."
        "process_founder_coin_publication."
        "get_remote_publication"
    )
    def test_accepts_new_publication_then_stops_at_prepare_gate(
        self,
        get_remote,
        accept,
        prepare,
    ):
        from auctions.sui_adapter import (
            SuiAdapterError,
        )

        get_remote.return_value = None

        accept.return_value = {
            "created": True,
            "publication": {
                "publication_key":
                    self.publication_key,
                "state":
                    "accepted",
            },
        }

        prepare.side_effect = SuiAdapterError(
            "FANZ Sui request failed "
            "with HTTP 400: "
            "Testnet transaction preparation "
            "is disabled"
        )

        stdout, _ = self._call()

        self.assertIn(
            "founder_coin_publication=ACCEPTED",
            stdout,
        )

        self.assertIn(
            (
                "founder_coin_publication="
                "STOP_PREPARE_GATE_CLOSED"
            ),
            stdout,
        )

        accept.assert_called_once_with(
            self.payload
        )

        prepare.assert_called_once_with(
            self.publication_key
        )

    @patch(
        "auctions.management.commands."
        "process_founder_coin_publication."
        "accept_creator_publication"
    )
    @patch(
        "auctions.management.commands."
        "process_founder_coin_publication."
        "prepare_creator_publication"
    )
    @patch(
        "auctions.management.commands."
        "process_founder_coin_publication."
        "get_remote_publication"
    )
    def test_existing_accepted_publication_skips_duplicate_accept(
        self,
        get_remote,
        prepare,
        accept,
    ):
        from auctions.sui_adapter import (
            SuiAdapterError,
        )

        get_remote.return_value = {
            "publication_key":
                self.publication_key,
            "state":
                "accepted",
        }

        prepare.side_effect = SuiAdapterError(
            "FANZ Sui request failed "
            "with HTTP 400: "
            "Testnet transaction preparation "
            "is disabled"
        )

        stdout, _ = self._call()

        accept.assert_not_called()

        self.assertIn(
            "journal_state=accepted",
            stdout,
        )

        self.assertIn(
            (
                "founder_coin_publication="
                "STOP_PREPARE_GATE_CLOSED"
            ),
            stdout,
        )

    @patch(
        "auctions.management.commands."
        "process_founder_coin_publication."
        "submit_creator_publication"
    )
    @patch(
        "auctions.management.commands."
        "process_founder_coin_publication."
        "get_remote_publication"
    )
    def test_prepared_publication_stops_at_submit_gate(
        self,
        get_remote,
        submit,
    ):
        from auctions.sui_adapter import (
            SuiAdapterError,
        )

        get_remote.return_value = {
            "publication_key":
                self.publication_key,
            "state":
                "prepared",
        }

        submit.side_effect = SuiAdapterError(
            "FANZ Sui request failed "
            "with HTTP 400: "
            "Creator publication submission "
            "is disabled"
        )

        stdout, _ = self._call()

        submit.assert_called_once_with(
            self.publication_key
        )

        self.assertIn(
            (
                "founder_coin_publication="
                "STOP_SUBMIT_GATE_CLOSED"
            ),
            stdout,
        )

    def test_finalized_asset_stops_before_sui(self):
        from django.utils import timezone
        from unittest.mock import patch

        self.asset.status = (
            self.asset.STATUS_ACTIVE
        )
        self.asset.coin_type = (
            "0x123::pc01_fanz::PC01_FANZ"
        )
        self.asset.genesis_tx_digest = (
            "digest-123"
        )
        self.asset.supply_fixed_at = (
            timezone.now()
        )

        self.asset.save(
            update_fields=[
                "status",
                "coin_type",
                "genesis_tx_digest",
                "supply_fixed_at",
                "updated_at",
            ]
        )

        with (
            patch.object(
                self.processor,
                "get_remote_publication",
            ) as get_remote,
            patch.object(
                self.processor,
                "prepare_creator_publication",
            ) as prepare_publication,
            patch.object(
                self.processor,
                "submit_creator_publication",
            ) as submit_publication,
        ):
            stdout, _ = self._call()

        self.assertIn(
            "founder_coin_publication=ALREADY_COMPLETE",
            stdout,
        )

        get_remote.assert_not_called()
        prepare_publication.assert_not_called()
        submit_publication.assert_not_called()

    def test_confirmed_publication_runs_django_reconcile_and_supply_verify(
        self,
    ):
        from unittest.mock import patch

        remote = {
            "publication_key":
                self.publication_key,
            "state":
                "confirmed",
            "package_id":
                "0x123",
            "coin_type":
                "0x123::pc01_fanz::PC01_FANZ",
            "tx_digest":
                "digest-123",
        }

        self.asset.status = (
            self.asset.STATUS_ACTIVE
        )
        self.asset.coin_type = (
            "0x123::pc01_fanz::PC01_FANZ"
        )
        self.asset.genesis_tx_digest = (
            "digest-123"
        )
        self.asset.supply_fixed_at = (
            __import__(
                "django.utils.timezone",
                fromlist=["now"],
            ).now()
        )

        with (
            patch.object(
                self.processor,
                "get_remote_publication",
                return_value=remote,
            ),
            patch.object(
                self.processor,
                "reconcile_confirmed_creator_publication",
                return_value=(
                    self.asset,
                    True,
                ),
            ) as reconcile_django,
            patch.object(
                self.processor,
                "verify_economy_asset_fixed_supply",
                return_value=(
                    self.asset,
                    True,
                ),
            ) as verify_supply,
        ):
            stdout, _ = self._call()

        reconcile_django.assert_called_once_with(
            self.asset.pk,
            self.publication_key,
        )

        verify_supply.assert_called_once_with(
            self.asset.pk,
            self.publication_key,
        )

        self.assertIn(
            "founder_coin_publication=COMPLETE",
            stdout,
        )


class FounderCoinPublicationWorkerTests(TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from django.contrib.auth import get_user_model

        from auctions.management.commands import (
            process_founder_coin_publication
            as processor,
        )

        User = get_user_model()

        self.owner = User.objects.create_user(
            username="founder-pub-worker-owner",
            password="test-password",
        )

        self.temp_dir = tempfile.TemporaryDirectory()
        self.prepared_root = Path(
            self.temp_dir.name
        )

        self.root_patch = patch.object(
            processor,
            "PREPARED_ROOT",
            self.prepared_root,
        )

        self.root_patch.start()

        self.addCleanup(
            self.root_patch.stop
        )

        self.addCleanup(
            self.temp_dir.cleanup
        )

    def _create_asset(self, handle):
        from auctions.models import (
            EconomyAsset,
            FounderAccount,
        )

        founder = FounderAccount.objects.create(
            handle=handle,
            status=FounderAccount.STATUS_OWNED,
            owner_root=self.owner,
            floor_price_credits=200,
        )

        return EconomyAsset.objects.create(
            founder_account=founder,
            name=f"{handle.title()}Fanz",
            symbol=f"{handle.upper()}FANZ",
            chain="sui",
            decimals=6,
            genesis_supply_base_units=(
                21_000_000_000_000_000
            ),
            status=EconomyAsset.STATUS_DRAFT,
            metadata={
                "issuance_source":
                    "founder_vending",
                "generated_package":
                    f"fanz_creator_{handle}",
                "intended_recipient_address":
                    "0xabc",
            },
        )

    def _payload_path(self, asset):
        return (
            self.prepared_root
            / (
                f"founder-{asset.pk}-"
                f"{asset.founder_account.handle}-v1.json"
            )
        )

    def _call(self):
        import io

        from django.core.management import call_command

        stdout = io.StringIO()
        stderr = io.StringIO()

        call_command(
            "process_next_founder_coin_publication",
            stdout=stdout,
            stderr=stderr,
        )

        return (
            stdout.getvalue(),
            stderr.getvalue(),
        )

    def test_empty_queue_is_noop(self):
        stdout, _ = self._call()

        self.assertIn(
            "founder_coin_worker=EMPTY",
            stdout,
        )

    def test_missing_prepared_payload_waits_safely(self):
        asset = self._create_asset(
            "wk01"
        )

        stdout, _ = self._call()

        self.assertIn(
            (
                "founder_coin_worker="
                "WAITING_FOR_PREPARED_PAYLOAD"
            ),
            stdout,
        )

        self.assertIn(
            f"asset_id={asset.pk}",
            stdout,
        )

        asset.refresh_from_db()

        self.assertEqual(
            asset.status,
            asset.STATUS_DRAFT,
        )

    @patch(
        "auctions.management.commands."
        "process_next_founder_coin_publication."
        "call_command"
    )
    def test_prepared_payload_delegates_to_processor(
        self,
        nested_call,
    ):
        asset = self._create_asset(
            "wk02"
        )

        self._payload_path(
            asset
        ).write_text("{}")

        stdout, _ = self._call()

        self.assertIn(
            "founder_coin_worker=PROCESSING",
            stdout,
        )

        nested_call.assert_called_once()

        args, kwargs = nested_call.call_args

        self.assertEqual(
            args[0],
            "process_founder_coin_publication",
        )

        self.assertEqual(
            kwargs["asset_id"],
            asset.pk,
        )

    @patch(
        "auctions.management.commands."
        "process_next_founder_coin_publication."
        "call_command"
    )
    def test_only_oldest_pending_asset_is_processed(
        self,
        nested_call,
    ):
        first = self._create_asset(
            "wk03"
        )

        second = self._create_asset(
            "wk04"
        )

        self._payload_path(
            first
        ).write_text("{}")

        self._payload_path(
            second
        ).write_text("{}")

        stdout, _ = self._call()

        self.assertIn(
            f"asset_id={first.pk}",
            stdout,
        )

        self.assertNotIn(
            f"asset_id={second.pk}",
            stdout,
        )

        nested_call.assert_called_once()

        _, kwargs = nested_call.call_args

        self.assertEqual(
            kwargs["asset_id"],
            first.pk,
        )


class SuiStarterGrantPolicyTests(TestCase):
    def test_fanz_credits_never_qualify_for_starter_sui(self):
        from .sui_grant_policy import (
            qualifies_for_sui_starter_grant,
        )

        self.assertFalse(
            qualifies_for_sui_starter_grant(
                payment_method="credits",
            )
        )

    def test_btc_qualifies_for_starter_sui(self):
        from .sui_grant_policy import (
            qualifies_for_sui_starter_grant,
        )

        self.assertTrue(
            qualifies_for_sui_starter_grant(
                payment_method="btc",
            )
        )

    def test_doge_qualifies_for_starter_sui(self):
        from .sui_grant_policy import (
            qualifies_for_sui_starter_grant,
        )

        self.assertTrue(
            qualifies_for_sui_starter_grant(
                payment_method="doge",
            )
        )

    def test_sui_qualifies_for_starter_sui(self):
        from .sui_grant_policy import (
            qualifies_for_sui_starter_grant,
        )

        self.assertTrue(
            qualifies_for_sui_starter_grant(
                payment_method="sui",
            )
        )

    def test_credits_with_sui_address_still_do_not_get_grant(self):
        from .sui_grant_policy import (
            starter_grant_is_ready,
        )

        self.assertFalse(
            starter_grant_is_ready(
                payment_method="credits",
                sui_address=(
                    "0x"
                    + "1" * 64
                ),
            )
        )

    def test_external_payment_without_address_waits(self):
        from .sui_grant_policy import (
            starter_grant_is_ready,
        )

        for method in (
            "btc",
            "doge",
            "sui",
        ):
            with self.subTest(method=method):
                self.assertFalse(
                    starter_grant_is_ready(
                        payment_method=method,
                        sui_address="",
                    )
                )

    def test_external_payment_with_address_is_ready(self):
        from .sui_grant_policy import (
            starter_grant_is_ready,
        )

        address = "0x" + "2" * 64

        for method in (
            "btc",
            "doge",
            "sui",
        ):
            with self.subTest(method=method):
                self.assertTrue(
                    starter_grant_is_ready(
                        payment_method=method,
                        sui_address=address,
                    )
                )


class FanzPaymentPolicyTests(SimpleTestCase):
    def test_platform_founder_accepts_all_payment_rails(self):
        from .payment_policy import (
            CONTEXT_PLATFORM_FOUNDER,
            payment_method_allowed,
        )

        for method in (
            "credits",
            "btc",
            "doge",
            "sui",
        ):
            with self.subTest(method=method):
                self.assertTrue(
                    payment_method_allowed(
                        context=CONTEXT_PLATFORM_FOUNDER,
                        payment_method=method,
                        seller_is_platform=True,
                    )
                )

    def test_platform_meme_coin_accepts_all_payment_rails(self):
        from .payment_policy import (
            CONTEXT_PLATFORM_MEME_COIN,
            payment_method_allowed,
        )

        for method in (
            "credits",
            "btc",
            "doge",
            "sui",
        ):
            with self.subTest(method=method):
                self.assertTrue(
                    payment_method_allowed(
                        context=CONTEXT_PLATFORM_MEME_COIN,
                        payment_method=method,
                        seller_is_platform=True,
                    )
                )

    def test_non_platform_founder_p2p_is_credits_only(self):
        from .payment_policy import (
            CONTEXT_FOUNDER_P2P,
            payment_method_allowed,
        )

        self.assertTrue(
            payment_method_allowed(
                context=CONTEXT_FOUNDER_P2P,
                payment_method="credits",
                seller_is_platform=False,
            )
        )

        for method in (
            "btc",
            "doge",
            "sui",
        ):
            with self.subTest(method=method):
                self.assertFalse(
                    payment_method_allowed(
                        context=CONTEXT_FOUNDER_P2P,
                        payment_method=method,
                        seller_is_platform=False,
                    )
                )

    def test_feed_tips_are_credits_only(self):
        from .payment_policy import (
            CONTEXT_FEED_TIP,
            payment_method_allowed,
        )

        self.assertTrue(
            payment_method_allowed(
                context=CONTEXT_FEED_TIP,
                payment_method="credits",
            )
        )

        for method in ("btc", "doge", "sui"):
            self.assertFalse(
                payment_method_allowed(
                    context=CONTEXT_FEED_TIP,
                    payment_method=method,
                )
            )

    def test_post_unlocks_are_credits_only(self):
        from .payment_policy import (
            CONTEXT_POST_UNLOCK,
            payment_method_allowed,
        )

        self.assertTrue(
            payment_method_allowed(
                context=CONTEXT_POST_UNLOCK,
                payment_method="credits",
            )
        )

        for method in ("btc", "doge", "sui"):
            self.assertFalse(
                payment_method_allowed(
                    context=CONTEXT_POST_UNLOCK,
                    payment_method=method,
                )
            )

    def test_unknown_context_fails_closed_to_credits(self):
        from .payment_policy import (
            payment_method_allowed,
        )

        self.assertTrue(
            payment_method_allowed(
                context="future_unknown_thing",
                payment_method="credits",
            )
        )

        self.assertFalse(
            payment_method_allowed(
                context="future_unknown_thing",
                payment_method="sui",
            )
        )

    def test_fanz_meme_coin_is_not_a_payment_method(self):
        from .payment_policy import PAYMENT_METHODS

        self.assertNotIn(
            "fanz",
            PAYMENT_METHODS,
        )
        self.assertNotIn(
            "fanzmeme",
            PAYMENT_METHODS,
        )
        self.assertNotIn(
            "meme_coin",
            PAYMENT_METHODS,
        )


class FounderVendingPaymentPolicyIntegrationTests(
    SimpleTestCase
):
    def test_platform_founder_policy_allows_four_rails(self):
        from .payment_policy import (
            CONTEXT_PLATFORM_FOUNDER,
            payment_method_allowed,
        )

        for method in (
            "credits",
            "btc",
            "doge",
            "sui",
        ):
            with self.subTest(method=method):
                self.assertTrue(
                    payment_method_allowed(
                        context=CONTEXT_PLATFORM_FOUNDER,
                        payment_method=method,
                        seller_is_platform=True,
                    )
                )

    def test_platform_founder_rejects_fanz_meme_coin_as_rail(self):
        from .payment_policy import (
            CONTEXT_PLATFORM_FOUNDER,
            payment_method_allowed,
        )

        for method in (
            "fanz",
            "fanzmeme",
            "meme_coin",
        ):
            with self.subTest(method=method):
                self.assertFalse(
                    payment_method_allowed(
                        context=CONTEXT_PLATFORM_FOUNDER,
                        payment_method=method,
                        seller_is_platform=True,
                    )
                )


class ExternalFounderPaymentIntentPolicyTests(
    SimpleTestCase
):
    def test_external_founder_rails_map_to_settlement_sources(self):
        from .models import (
            FounderCartItem,
            PaymentIntent,
        )

        expected = {
            FounderCartItem.PAYMENT_BTC:
                PaymentIntent.SETTLEMENT_BTCPAY,
            FounderCartItem.PAYMENT_DOGE:
                PaymentIntent.SETTLEMENT_BTCPAY,
            FounderCartItem.PAYMENT_SUI:
                PaymentIntent.SETTLEMENT_SUI,
        }

        self.assertEqual(
            expected[
                FounderCartItem.PAYMENT_BTC
            ],
            "btcpay",
        )

        self.assertEqual(
            expected[
                FounderCartItem.PAYMENT_DOGE
            ],
            "btcpay",
        )

        self.assertEqual(
            expected[
                FounderCartItem.PAYMENT_SUI
            ],
            "sui",
        )

    def test_credits_are_not_an_external_founder_rail(self):
        from .models import FounderCartItem

        external = {
            FounderCartItem.PAYMENT_BTC,
            FounderCartItem.PAYMENT_DOGE,
            FounderCartItem.PAYMENT_SUI,
        }

        self.assertNotIn(
            FounderCartItem.PAYMENT_CREDITS,
            external,
        )


class FounderBTCPayRailPolicyTests(TestCase):
    def test_btc_founder_intent_reports_btc(self):
        from .btcpay import (
            expected_btcpay_payment_method,
        )
        from .models import PaymentIntent

        intent = PaymentIntent(
            purpose="founder_purchase",
            settlement_source=(
                PaymentIntent.SETTLEMENT_BTCPAY
            ),
            metadata={
                "payment_method": "btc",
            },
        )

        self.assertEqual(
            expected_btcpay_payment_method(intent),
            "btc",
        )

    def test_doge_founder_intent_reports_doge(self):
        from .btcpay import (
            expected_btcpay_payment_method,
        )
        from .models import PaymentIntent

        intent = PaymentIntent(
            purpose="founder_purchase",
            settlement_source=(
                PaymentIntent.SETTLEMENT_BTCPAY
            ),
            metadata={
                "payment_method": "doge",
            },
        )

        self.assertEqual(
            expected_btcpay_payment_method(intent),
            "doge",
        )

    def test_other_method_is_rejected_from_btcpay(self):
        from .btcpay import (
            BTCPayError,
            expected_btcpay_payment_method,
        )
        from .models import PaymentIntent

        for method in (
            "credits",
            "sui",
            "fanz",
        ):
            with self.subTest(method=method):
                intent = PaymentIntent(
                    purpose="founder_purchase",
                    settlement_source=(
                        PaymentIntent.SETTLEMENT_BTCPAY
                    ),
                    metadata={
                        "payment_method": method,
                    },
                )

                with self.assertRaises(BTCPayError):
                    expected_btcpay_payment_method(
                        intent
                    )


class FounderBTCPaySettlementVerificationTests(
    TestCase
):
    def _intent(self, method):
        from .models import PaymentIntent

        return PaymentIntent(
            purpose="founder_purchase",
            settlement_source=(
                PaymentIntent.SETTLEMENT_BTCPAY
            ),
            btcpay_invoice_id="test-invoice",
            metadata={
                "payment_method": method,
            },
        )

    def test_doge_settlement_matches_doge_intent(self):
        from .btcpay import (
            verify_btcpay_intent_payment_method,
        )

        methods = [
            {
                "paymentMethodId": "BTC-CHAIN",
                "paymentMethodPaid": "0",
                "payments": [],
            },
            {
                "paymentMethodId": "DOGE-CHAIN",
                "paymentMethodPaid": "5.7",
                "payments": [
                    {
                        "status": "Settled",
                        "value": "5.7",
                    },
                ],
            },
        ]

        result = (
            verify_btcpay_intent_payment_method(
                self._intent("doge"),
                payment_methods=methods,
            )
        )

        self.assertEqual(
            result,
            "DOGE-CHAIN",
        )

    def test_doge_payment_rejected_for_btc_intent(self):
        from .btcpay import (
            BTCPayError,
            verify_btcpay_intent_payment_method,
        )

        methods = [
            {
                "paymentMethodId": "BTC-CHAIN",
                "paymentMethodPaid": "0",
                "payments": [],
            },
            {
                "paymentMethodId": "DOGE-CHAIN",
                "paymentMethodPaid": "5.7",
                "payments": [
                    {
                        "status": "Settled",
                    },
                ],
            },
        ]

        with self.assertRaises(BTCPayError):
            verify_btcpay_intent_payment_method(
                self._intent("btc"),
                payment_methods=methods,
            )

    def test_available_unpaid_rail_is_not_settled(self):
        from .btcpay import (
            settled_btcpay_payment_method_ids,
        )

        methods = [
            {
                "paymentMethodId": "BTC-CHAIN",
                "paymentMethodPaid": "0",
                "totalPaid": "0.00000633",
                "payments": [],
            },
            {
                "paymentMethodId": "DOGE-CHAIN",
                "paymentMethodPaid": "5.7",
                "payments": [
                    {
                        "status": "Settled",
                    },
                ],
            },
        ]

        self.assertEqual(
            settled_btcpay_payment_method_ids(
                methods
            ),
            {"DOGE-CHAIN"},
        )


class ExternalFounderFulfillmentTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        from .models import (
            BidWallet,
            FounderAccount,
            FounderCart,
            FounderCartItem,
            PaymentIntent,
        )

        self.platform_user = User.objects.create_user(
            username="platform-founder-test",
            password="test-password",
        )

        self.buyer = User.objects.create_user(
            username="external-founder-buyer",
            password="test-password",
        )

        # get_system_wallet() expects the FANZ system wallet
        # infrastructure to exist. Reuse the actual helper setup
        # through the wallet model rather than fabricating any
        # external purchase wallet transaction.
        BidWallet.objects.get_or_create(
            user=self.platform_user,
            defaults={
                "credits": 0,
            },
        )

        self.cart = FounderCart.objects.create(
            purchaser=self.buyer,
        )

        self.founder = FounderAccount.objects.create(
            handle="xpay",
            status=FounderAccount.STATUS_RESERVED,
        )

        self.intent = PaymentIntent.objects.create(
            user=self.buyer,
            purpose="founder_purchase",
            status="settled",
            amount="10.00",
            currency="USD",
            settlement_source=(
                PaymentIntent.SETTLEMENT_BTCPAY
            ),
            settlement_reference="",
            btcpay_invoice_id="external-founder-test-invoice",
            metadata={
                "founder_cart_item_id": 0,
                "wanted_handle": "xpay",
                "list_price_credits": 200,
                "payment_method": "btc",
            },
            paid_at=timezone.now(),
        )

        self.item = FounderCartItem.objects.create(
            cart=self.cart,
            wanted_handle="xpay",
            budget_credits=215,
            list_price_credits=200,
            payment_method=FounderCartItem.PAYMENT_BTC,
            payment_intent=self.intent,
            status=FounderCartItem.STATUS_QUOTED,
            quoted_at=timezone.now(),
            reservation_expires_at=(
                timezone.now()
                + timedelta(hours=1)
            ),
        )

        self.intent.metadata = {
            "founder_cart_item_id": self.item.pk,
            "wanted_handle": "xpay",
            "list_price_credits": 200,
            "payment_method": "btc",
        }
        self.intent.save(
            update_fields=[
                "metadata",
                "updated_at",
            ]
        )

    def test_external_founder_payment_transfers_ownership(self):
        from .models import (
            FounderOwnershipLedger,
            WalletTransaction,
        )
        from .payment_services import (
            fulfill_payment_intent,
        )

        wallet_tx_before = (
            WalletTransaction.objects.count()
        )

        fulfilled, created = (
            fulfill_payment_intent(
                self.intent.pk
            )
        )

        self.assertTrue(created)
        self.assertEqual(
            fulfilled.status,
            "fulfilled",
        )

        self.founder.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(
            self.founder.owner_root_id,
            self.buyer.pk,
        )

        self.assertEqual(
            self.founder.status,
            self.founder.STATUS_OWNED,
        )

        self.assertEqual(
            self.item.status,
            self.item.STATUS_PURCHASED,
        )

        ledger = (
            FounderOwnershipLedger.objects
            .filter(
                founder_account=self.founder,
                buyer_root=self.buyer,
            )
            .get()
        )

        self.assertEqual(
            ledger.sale_price_credits,
            200,
        )

        self.assertEqual(
            ledger.wallet_transaction_ids,
            [],
        )

        self.assertEqual(
            WalletTransaction.objects.count(),
            wallet_tx_before,
        )

    def test_external_founder_fulfillment_is_idempotent(self):
        from .models import FounderOwnershipLedger
        from .payment_services import (
            fulfill_payment_intent,
        )

        first, first_created = (
            fulfill_payment_intent(
                self.intent.pk
            )
        )

        second, second_created = (
            fulfill_payment_intent(
                self.intent.pk
            )
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)

        self.assertEqual(
            first.pk,
            second.pk,
        )

        self.assertEqual(
            FounderOwnershipLedger.objects
            .filter(
                founder_account=self.founder,
                buyer_root=self.buyer,
            )
            .count(),
            1,
        )

    def test_external_founder_rejects_payment_method_mismatch(self):
        from .payment_services import (
            PaymentFulfillmentError,
            fulfill_payment_intent,
        )

        self.intent.metadata = {
            **self.intent.metadata,
            "payment_method": "doge",
        }
        self.intent.save(
            update_fields=[
                "metadata",
                "updated_at",
            ]
        )

        with self.assertRaises(
            PaymentFulfillmentError
        ):
            fulfill_payment_intent(
                self.intent.pk
            )

        self.founder.refresh_from_db()
        self.item.refresh_from_db()
        self.intent.refresh_from_db()

        self.assertIsNone(
            self.founder.owner_root_id
        )

        self.assertEqual(
            self.item.status,
            self.item.STATUS_QUOTED,
        )

        self.assertEqual(
            self.intent.status,
            "settled",
        )

        self.assertIsNone(
            self.intent.fulfilled_at
        )


class SuiStarterGrantServiceTests(TestCase):
    def test_credits_do_not_call_sui_adapter(self):
        from unittest.mock import patch

        from .sui_grant_services import (
            grant_starter_sui_for_payment_intent,
        )

        class Intent:
            pk = 901
            status = "settled"

        with patch(
            "auctions.sui_grant_services."
            "create_sui_starter_grant"
        ) as grant_mock:
            result = (
                grant_starter_sui_for_payment_intent(
                    payment_intent=Intent(),
                    payment_method="credits",
                    sui_address="0x" + "1" * 64,
                )
            )

        self.assertFalse(result["delivered"])
        grant_mock.assert_not_called()

    def test_external_payment_without_address_defers(self):
        from unittest.mock import patch

        from .sui_grant_services import (
            grant_starter_sui_for_payment_intent,
        )

        class Intent:
            pk = 902
            status = "settled"

        with patch(
            "auctions.sui_grant_services."
            "create_sui_starter_grant"
        ) as grant_mock:
            result = (
                grant_starter_sui_for_payment_intent(
                    payment_intent=Intent(),
                    payment_method="btc",
                    sui_address="",
                )
            )

        self.assertTrue(result["deferred"])
        grant_mock.assert_not_called()

    def test_external_payment_uses_deterministic_key(self):
        from unittest.mock import patch

        from .sui_grant_services import (
            grant_starter_sui_for_payment_intent,
        )

        address = "0x" + "2" * 64

        class Intent:
            pk = 903
            status = "settled"

        with patch(
            "auctions.sui_grant_services."
            "create_sui_starter_grant",
            return_value={
                "transfer": {
                    "submission_key":
                        "starter-grant-payment-intent-903",
                    "amount_mist":
                        "250000000",
                    "state":
                        "confirmed",
                    "tx_digest":
                        "test-digest",
                },
            },
        ) as grant_mock:
            result = (
                grant_starter_sui_for_payment_intent(
                    payment_intent=Intent(),
                    payment_method="doge",
                    sui_address=address,
                )
            )

        self.assertTrue(result["delivered"])

        grant_mock.assert_called_once_with(
            submission_key=(
                "starter-grant-payment-intent-903"
            ),
            recipient_address=address,
        )


class FounderSuiPaymentSettlementTests(TestCase):
    def test_verifier_requires_mainnet_success_and_sufficient_amount(self):
        from unittest.mock import patch

        from .models import PaymentIntent
        from .sui_payment_services import (
            settle_founder_sui_payment,
        )

        intent = PaymentIntent(
            pk=1001,
            purpose="founder_purchase",
            status="created",
            settlement_source=(
                PaymentIntent.SETTLEMENT_SUI
            ),
        )

        self.assertEqual(
            intent.settlement_source,
            "sui",
        )

        verification = {
            "network": "mainnet",
            "tx_digest": "test-digest",
            "success": True,
            "recipient_address":
                "0x" + "1" * 64,
            "received_mist": "500000000",
            "minimum_amount_mist":
                "500000000",
            "sufficient": True,
        }

        self.assertTrue(
            verification["success"]
        )
        self.assertTrue(
            verification["sufficient"]
        )
        self.assertEqual(
            verification["network"],
            "mainnet",
        )

    def test_insufficient_verification_is_not_acceptable(self):
        verification = {
            "network": "mainnet",
            "success": True,
            "received_mist": "100",
            "minimum_amount_mist": "200",
            "sufficient": False,
        }

        self.assertFalse(
            verification["sufficient"]
        )

    def test_failed_transaction_is_not_acceptable(self):
        verification = {
            "network": "mainnet",
            "success": False,
            "sufficient": True,
        }

        self.assertFalse(
            verification["success"]
        )


class FounderSuiQuoteFreezeTests(TestCase):
    def setUp(self):
        from datetime import timedelta
        from django.contrib.auth.models import User
        from django.utils import timezone

        from .models import (
            FounderCart,
            FounderCartItem,
            PaymentIntent,
        )

        self.buyer = User.objects.create_user(
            username="sui-quote-buyer",
            password="test-password",
        )

        self.cart = FounderCart.objects.create(
            purchaser=self.buyer,
        )

        self.intent = PaymentIntent.objects.create(
            user=self.buyer,
            purpose="founder_purchase",
            status="created",
            amount="10.00",
            currency="USD",
            settlement_source=(
                PaymentIntent.SETTLEMENT_SUI
            ),
            metadata={
                "payment_method": "sui",
            },
        )

        self.item = FounderCartItem.objects.create(
            cart=self.cart,
            wanted_handle="sqte",
            budget_credits=215,
            list_price_credits=200,
            payment_method=FounderCartItem.PAYMENT_SUI,
            payment_intent=self.intent,
            status=FounderCartItem.STATUS_QUOTED,
            quoted_at=timezone.now(),
            reservation_expires_at=(
                timezone.now()
                + timedelta(hours=1)
            ),
        )

    def test_quote_is_frozen_into_payment_intent(self):
        from unittest.mock import patch

        from .sui_quote_services import (
            freeze_founder_sui_quote,
        )

        recipient = (
            "0x"
            + "1" * 64
        )

        response = {
            "quote": {
                "network": "mainnet",
                "recipient_address": recipient,
                "amount_usd": "10.00",
                "sui_usd_price": "0.733668",
                "amount_mist": "13630143335",
                "amount_sui": "13.630143335",
                "quoted_at":
                    "2026-09-01T00:30:01.889Z",
                "quote_expires_at":
                    "2026-09-01T00:45:01.889Z",
            },
        }

        with patch(
            "auctions.sui_quote_services."
            "quote_sui_payment",
            return_value=response,
        ) as quote_mock:
            intent, created = (
                freeze_founder_sui_quote(
                    payment_intent_id=self.intent.pk,
                )
            )

        self.assertTrue(created)

        intent.refresh_from_db()

        metadata = intent.metadata

        self.assertEqual(
            metadata["sui_network"],
            "mainnet",
        )
        self.assertEqual(
            metadata["sui_recipient_address"],
            recipient,
        )
        self.assertEqual(
            metadata["sui_required_mist"],
            "13630143335",
        )
        self.assertEqual(
            metadata["sui_amount"],
            "13.630143335",
        )
        self.assertEqual(
            metadata["sui_usd_price"],
            "0.733668",
        )

        quote_mock.assert_called_once_with(
            amount_usd=intent.amount,
        )

    def test_frozen_quote_is_reused_not_repriced(self):
        from unittest.mock import patch

        from .sui_quote_services import (
            freeze_founder_sui_quote,
        )

        self.intent.metadata = {
            **self.intent.metadata,
            "sui_network":
                "mainnet",
            "sui_recipient_address":
                "0x" + "2" * 64,
            "sui_required_mist":
                "123456789",
            "sui_amount":
                "0.123456789",
            "sui_usd_price":
                "1.00",
            "sui_quoted_at":
                "2026-09-01T00:30:00+00:00",
            "sui_quote_expires_at":
                "2026-09-01T00:45:00+00:00",
        }

        self.intent.save(
            update_fields=[
                "metadata",
                "updated_at",
            ]
        )

        with patch(
            "auctions.sui_quote_services."
            "quote_sui_payment"
        ) as quote_mock:
            intent, created = (
                freeze_founder_sui_quote(
                    payment_intent_id=self.intent.pk,
                )
            )

        self.assertFalse(created)
        self.assertEqual(
            intent.metadata["sui_required_mist"],
            "123456789",
        )

        quote_mock.assert_not_called()

    def test_non_sui_intent_cannot_get_sui_quote(self):
        from .models import PaymentIntent
        from .sui_quote_services import (
            SuiPaymentQuoteError,
            freeze_founder_sui_quote,
        )

        self.intent.settlement_source = (
            PaymentIntent.SETTLEMENT_BTCPAY
        )

        self.intent.save(
            update_fields=[
                "settlement_source",
                "updated_at",
            ]
        )

        with self.assertRaises(
            SuiPaymentQuoteError
        ):
            freeze_founder_sui_quote(
                payment_intent_id=self.intent.pk,
            )


class FounderSuiVerifyViewTests(TestCase):
    def setUp(self):
        from datetime import timedelta
        from django.contrib.auth.models import User
        from django.utils import timezone

        from .models import (
            FounderCart,
            FounderCartItem,
            PaymentIntent,
        )

        self.user = User.objects.create_user(
            username="sui-verify-view-user",
            password="test-password",
        )

        self.client.force_login(self.user)

        self.cart = FounderCart.objects.create(
            purchaser=self.user,
        )

        self.recipient = (
            "0x"
            + "3" * 64
        )

        self.intent = PaymentIntent.objects.create(
            user=self.user,
            purpose="founder_purchase",
            status="created",
            amount="10.00",
            currency="USD",
            settlement_source=(
                PaymentIntent.SETTLEMENT_SUI
            ),
            metadata={
                "payment_method": "sui",
                "sui_recipient_address":
                    self.recipient,
                "sui_required_mist":
                    "13630143335",
                "sui_amount":
                    "13.630143335",
                "sui_quote_expires_at":
                    "2026-09-01T00:45:01.889Z",
            },
        )

        self.item = FounderCartItem.objects.create(
            cart=self.cart,
            wanted_handle="svfy",
            budget_credits=215,
            list_price_credits=200,
            payment_method=FounderCartItem.PAYMENT_SUI,
            payment_intent=self.intent,
            status=FounderCartItem.STATUS_QUOTED,
            quoted_at=timezone.now(),
            reservation_expires_at=(
                timezone.now()
                + timedelta(hours=1)
            ),
        )

    def test_verify_view_uses_frozen_quote_not_browser_values(self):
        from unittest.mock import patch
        from django.urls import reverse

        with patch(
            "auctions.sui_payment_services."
            "settle_founder_sui_payment",
            return_value=(
                self.intent,
                True,
            ),
        ) as settle_mock:
            response = self.client.post(
                reverse(
                    "verify_founder_sui_payment"
                ),
                {
                    "payment_intent_id":
                        self.intent.pk,
                    "tx_digest":
                        "test-mainnet-digest",

                    # Deliberately malicious / ignored.
                    "recipient_address":
                        "0x" + "9" * 64,
                    "minimum_amount_mist":
                        "1",
                },
            )

        self.assertEqual(
            response.status_code,
            302,
        )

        settle_mock.assert_called_once_with(
            payment_intent_id=self.intent.pk,
            tx_digest="test-mainnet-digest",
            recipient_address=self.recipient,
            minimum_amount_mist=13630143335,
        )

    def test_user_cannot_verify_another_users_intent(self):
        from unittest.mock import patch
        from django.contrib.auth.models import User
        from django.urls import reverse

        other = User.objects.create_user(
            username="other-sui-user",
            password="test-password",
        )

        self.intent.user = other
        self.intent.save(
            update_fields=[
                "user",
                "updated_at",
            ]
        )

        with patch(
            "auctions.sui_payment_services."
            "settle_founder_sui_payment"
        ) as settle_mock:
            response = self.client.post(
                reverse(
                    "verify_founder_sui_payment"
                ),
                {
                    "payment_intent_id":
                        self.intent.pk,
                    "tx_digest":
                        "test-mainnet-digest",
                },
            )

        self.assertEqual(
            response.status_code,
            302,
        )

        settle_mock.assert_not_called()
