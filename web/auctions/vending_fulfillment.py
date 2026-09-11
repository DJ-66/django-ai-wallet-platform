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


FULFILLMENT_HANDLERS = {
    "credit_package": fulfill_credit_package,
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
