from .models import PaymentIntent


class VendingFulfillmentError(RuntimeError):
    pass


def _settlement_external_id(intent):
    if (
        intent.settlement_source
        == PaymentIntent.SETTLEMENT_BTCPAY
    ):
        if not intent.btcpay_invoice_id:
            raise VendingFulfillmentError(
                "Vending purchase has no "
                "BTCPay invoice id."
            )

        return (
            f"btcpay:{intent.btcpay_invoice_id}"
        )

    if (
        intent.settlement_source
        == PaymentIntent.SETTLEMENT_SUI
    ):
        digest = str(
            intent.settlement_reference or ""
        ).strip()

        if not digest:
            raise VendingFulfillmentError(
                "Vending purchase has no "
                "SUI transaction digest."
            )

        return f"sui:{digest}"

    raise VendingFulfillmentError(
        "Vending purchase has unsupported "
        "settlement source."
    )


def fulfill_credit_package(intent):
    from .services import process_credit_purchase

    if intent.user_id is None:
        raise VendingFulfillmentError(
            "Credit purchase has no user."
        )

    if intent.credit_package_id is None:
        raise VendingFulfillmentError(
            "Credit purchase has no CreditPackage."
        )

    external_id = _settlement_external_id(
        intent
    )

    process_credit_purchase(
        user=intent.user,
        package=intent.credit_package,
        external_id=external_id,
    )

    return True


def fulfill_sui_coin_delivery(intent):
    from .models import (
        EconomyAsset,
        EconomyAssetDelivery,
    )

    product = intent.vending_product

    if product is None:
        raise VendingFulfillmentError(
            "SUI coin delivery has no "
            "VendingProduct."
        )

    product_metadata = (
        product.fulfillment_metadata or {}
    )
    intent_metadata = intent.metadata or {}

    try:
        economy_asset_id = int(
            product_metadata[
                "economy_asset_id"
            ]
        )
        amount_base_units = int(
            product_metadata[
                "amount_base_units"
            ]
        )
        recipient_address = str(
            intent_metadata[
                "recipient_address"
            ]
        ).strip()
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise VendingFulfillmentError(
            "SUI coin vending has invalid "
            "fulfillment metadata."
        ) from exc

    if amount_base_units <= 0:
        raise VendingFulfillmentError(
            "SUI coin vending amount "
            "must be positive."
        )

    if not recipient_address:
        raise VendingFulfillmentError(
            "SUI coin vending has no "
            "recipient address."
        )

    try:
        asset = EconomyAsset.objects.get(
            pk=economy_asset_id,
            status=EconomyAsset.STATUS_ACTIVE,
        )
    except EconomyAsset.DoesNotExist as exc:
        raise VendingFulfillmentError(
            "SUI coin vending references no "
            "active EconomyAsset."
        ) from exc

    delivery, created = (
        EconomyAssetDelivery.objects
        .get_or_create(
            payment_intent=intent,
            defaults={
                "asset": asset,
                "recipient_address":
                    recipient_address,
                "amount_base_units":
                    amount_base_units,
            },
        )
    )

    if not created:
        if (
            delivery.asset_id != asset.pk
            or delivery.recipient_address
            != recipient_address
            or delivery.amount_base_units
            != amount_base_units
        ):
            raise VendingFulfillmentError(
                "Existing SUI coin delivery "
                "does not match vending "
                "fulfillment data."
            )

    # Creating the durable blockchain obligation
    # is not final fulfillment. The existing Sui
    # delivery processor must prepare, submit,
    # and confirm it.
    return False


FULFILLMENT_HANDLERS = {
    "credit_package":
        fulfill_credit_package,
    "sui_coin_delivery":
        fulfill_sui_coin_delivery,
}


def dispatch_vending_fulfillment(intent):
    product = intent.vending_product

    if product is None:
        raise VendingFulfillmentError(
            "PaymentIntent has no VendingProduct."
        )

    fulfillment_type = str(
        product.fulfillment_type or ""
    ).strip().lower()

    handler = FULFILLMENT_HANDLERS.get(
        fulfillment_type
    )

    if handler is None:
        raise VendingFulfillmentError(
            "No vending fulfillment handler for "
            f"type: {fulfillment_type}"
        )

    return handler(intent)
