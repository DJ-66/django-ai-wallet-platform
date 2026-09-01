from django.db import transaction
from django.utils import timezone

from .models import (
    EconomyAsset,
    EconomyAssetDelivery,
    PaymentIntent,
)
from .services import process_credit_purchase
from .founder_cart_services import (
    FounderCartError,
    fulfill_external_founder_vending_purchase,
)


class PaymentFulfillmentError(RuntimeError):
    pass


def dispatch_payment_fulfillment(intent):
    """
    Deliver the FANZ value associated with a settled PaymentIntent.

    Settlement validation, locking, idempotency, and final fulfillment state
    are owned by fulfill_payment_intent(). This dispatcher is responsible only
    for purpose-specific delivery.
    """
    if intent.purpose == "credit_purchase":
        if intent.user_id is None:
            raise PaymentFulfillmentError(
                "Credit purchase has no user."
            )

        if intent.credit_package_id is None:
            raise PaymentFulfillmentError(
                "Credit purchase has no CreditPackage."
            )

        process_credit_purchase(
            user=intent.user,
            package=intent.credit_package,
            external_id=f"btcpay:{intent.btcpay_invoice_id}",
        )

        return True

    elif intent.purpose == "founder_purchase":
        try:
            fulfill_external_founder_vending_purchase(
                payment_intent=intent,
            )
        except FounderCartError as exc:
            raise PaymentFulfillmentError(
                str(exc)
            ) from exc

        return True

    elif intent.purpose == "donation":
        # Settlement itself is the fulfillment for a donation.
        # Donations deliberately mint no FANZ Credits.
        return True

    elif intent.purpose == "integration_test":
        # Integration tests deliberately have no economic fulfillment.
        return True

    elif intent.purpose == "economy_asset_purchase":
        metadata = intent.metadata or {}

        try:
            economy_asset_id = int(metadata["economy_asset_id"])
            amount_base_units = int(metadata["amount_base_units"])
            recipient_address = str(metadata["recipient_address"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise PaymentFulfillmentError(
                "Economy asset purchase has invalid fulfillment metadata."
            ) from exc

        if amount_base_units <= 0:
            raise PaymentFulfillmentError(
                "Economy asset purchase amount must be positive."
            )

        if not recipient_address:
            raise PaymentFulfillmentError(
                "Economy asset purchase has no recipient address."
            )

        try:
            asset = EconomyAsset.objects.get(
                pk=economy_asset_id,
                status=EconomyAsset.STATUS_ACTIVE,
            )
        except EconomyAsset.DoesNotExist as exc:
            raise PaymentFulfillmentError(
                "Economy asset purchase references no active EconomyAsset."
            ) from exc

        delivery, created = EconomyAssetDelivery.objects.get_or_create(
            payment_intent=intent,
            defaults={
                "asset": asset,
                "recipient_address": recipient_address,
                "amount_base_units": amount_base_units,
            },
        )

        if not created:
            if (
                delivery.asset_id != asset.pk
                or delivery.recipient_address != recipient_address
                or delivery.amount_base_units != amount_base_units
            ):
                raise PaymentFulfillmentError(
                    "Existing economy delivery does not match PaymentIntent metadata."
                )

        # Delivery is durable but not yet complete.
        # A separate blockchain processor must confirm it before this
        # PaymentIntent can transition to fulfilled.
        return False

    else:
        raise PaymentFulfillmentError(
            f"No fulfillment handler for purpose: {intent.purpose}"
        )


@transaction.atomic
def fulfill_payment_intent(payment_intent_id):
    intent = (
        PaymentIntent.objects
        .select_for_update()
        .get(pk=payment_intent_id)
    )

    # Already completed: safe no-op.
    if intent.fulfilled_at is not None:
        return intent, False

    if intent.status != "settled":
        raise PaymentFulfillmentError(
            "PaymentIntent must be settled before fulfillment."
        )

    if (
        intent.settlement_source
        == PaymentIntent.SETTLEMENT_BTCPAY
    ):
        if not intent.btcpay_invoice_id:
            raise PaymentFulfillmentError(
                "BTCPay PaymentIntent has no invoice id."
            )

    elif (
        intent.settlement_source
        == PaymentIntent.SETTLEMENT_SUI
    ):
        if not intent.settlement_reference:
            raise PaymentFulfillmentError(
                "Sui PaymentIntent has no transaction digest."
            )

    elif (
        intent.settlement_source
        == PaymentIntent.SETTLEMENT_INTERNAL
    ):
        # Internal settlement has no external transaction
        # identifier requirement.
        pass

    else:
        raise PaymentFulfillmentError(
            "PaymentIntent has an unsupported "
            "settlement source."
        )

    fulfillment_complete = dispatch_payment_fulfillment(intent)

    if not fulfillment_complete:
        return intent, False

    intent.status = "fulfilled"
    intent.fulfilled_at = timezone.now()

    intent.save(
        update_fields=[
            "status",
            "fulfilled_at",
            "updated_at",
        ]
    )

    return intent, True
