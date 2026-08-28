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

    @override_settings(FANZ_SUI_API_TOKEN="")
    def test_missing_configuration_is_rejected(self):
        from auctions.sui_adapter import (
            SuiAdapterError,
            get_delivery,
        )

        with self.assertRaises(SuiAdapterError):
            get_delivery("test-key")


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
