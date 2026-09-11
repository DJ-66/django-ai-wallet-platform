from decimal import Decimal

from .models import PaymentIntent, VendingProduct
from .payment_policy import (
    PAYMENT_BTC,
    PAYMENT_DOGE,
    PAYMENT_SUI,
    normalize_payment_method,
    seller_is_platform,
)


class VendingProductError(RuntimeError):
    pass


EXTERNAL_PAY_METHODS = frozenset({
    PAYMENT_BTC,
    PAYMENT_SUI,
    PAYMENT_DOGE,
})


SETTLEMENT_SOURCE_BY_PAYMENT_METHOD = {
    PAYMENT_BTC:
        PaymentIntent.SETTLEMENT_BTCPAY,
    PAYMENT_DOGE:
        PaymentIntent.SETTLEMENT_BTCPAY,
    PAYMENT_SUI:
        PaymentIntent.SETTLEMENT_SUI,
}


def create_vending_payment_intent(
    *,
    product,
    buyer,
    payment_method,
    purpose,
    credit_package=None,
    metadata=None,
):
    """
    Create the authoritative PaymentIntent for one
    FANZ vending purchase.

    Phase 1 supports only active PAY products sold
    through FANZ platform settlement rails.

    Rail-specific checkout preparation remains outside
    this service:
        BTC/DOGE -> BTCPay invoice creation
        SUI      -> quote freezing
    """
    if product is None:
        raise VendingProductError(
            "Vending product is required."
        )

    if not product.is_active:
        raise VendingProductError(
            "Vending product is inactive."
        )

    if product.mode != VendingProduct.MODE_PAY:
        raise VendingProductError(
            "Vending product is not a PAY product."
        )

    if (
        product.settlement_mode
        != VendingProduct.SETTLEMENT_PLATFORM
    ):
        raise VendingProductError(
            "Vending product is not configured for "
            "FANZ platform settlement."
        )

    if not seller_is_platform(product.seller):
        raise VendingProductError(
            "Vending seller is not authorized for "
            "FANZ platform settlement."
        )

    method = normalize_payment_method(
        payment_method
    )

    if method not in EXTERNAL_PAY_METHODS:
        raise VendingProductError(
            "Unsupported vending payment method."
        )

    if product.price_usd is None:
        raise VendingProductError(
            "Vending product has no USD price."
        )

    price = Decimal(product.price_usd)

    if price <= 0:
        raise VendingProductError(
            "Vending product price must be positive."
        )

    intent_metadata = dict(
        metadata or {}
    )

    intent_metadata["payment_method"] = (
        method
    )

    return PaymentIntent.objects.create(
        user=buyer,
        purpose=purpose,
        amount=price,
        currency="USD",
        settlement_source=(
            SETTLEMENT_SOURCE_BY_PAYMENT_METHOD[
                method
            ]
        ),
        vending_product=product,
        credit_package=credit_package,
        metadata=intent_metadata,
    )


def prepare_vending_checkout(
    *,
    payment_intent,
):
    """
    Prepare the external checkout for an existing
    FANZ vending PaymentIntent.

    BTC/DOGE delegate to the existing BTCPay primitive.
    SUI delegates to the existing generic SUI quote
    primitive.

    Settlement and fulfillment remain separate.
    """
    if not isinstance(
        payment_intent,
        PaymentIntent,
    ):
        raise TypeError(
            "payment_intent must be a PaymentIntent"
        )

    method = normalize_payment_method(
        (payment_intent.metadata or {}).get(
            "payment_method"
        )
    )

    if method in {
        PAYMENT_BTC,
        PAYMENT_DOGE,
    }:
        from .btcpay import (
            BTCPayError,
            create_payment_intent_invoice,
        )

        try:
            return create_payment_intent_invoice(
                payment_intent
            )
        except BTCPayError as exc:
            raise VendingProductError(
                str(exc)
            ) from exc

    if method == PAYMENT_SUI:
        from .sui_quote_services import (
            SuiPaymentQuoteError,
            freeze_sui_quote,
        )

        try:
            intent, _ = freeze_sui_quote(
                payment_intent_id=(
                    payment_intent.pk
                ),
            )
        except SuiPaymentQuoteError as exc:
            raise VendingProductError(
                str(exc)
            ) from exc

        return intent

    raise VendingProductError(
        "Unsupported vending payment method."
    )
