from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import (
    FounderCartItem,
    PaymentIntent,
)
from .sui_adapter import (
    SuiAdapterError,
    quote_sui_payment,
)


class SuiPaymentQuoteError(RuntimeError):
    pass


def _parse_quote_datetime(value):
    value = str(value or "").strip()

    if not value:
        raise SuiPaymentQuoteError(
            "SUI quote has no expiration time."
        )

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise SuiPaymentQuoteError(
            "SUI quote has invalid expiration time."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=dt_timezone.utc
        )

    return parsed


@transaction.atomic
def freeze_founder_sui_quote(
    *,
    payment_intent_id,
):
    """
    Obtain and freeze the authoritative SUI payment quote
    for one Founder PaymentIntent.

    The browser never chooses the recipient or SUI amount.
    """

    intent = (
        PaymentIntent.objects
        .select_for_update()
        .get(pk=payment_intent_id)
    )

    if intent.purpose != "founder_purchase":
        raise SuiPaymentQuoteError(
            "PaymentIntent is not a Founder purchase."
        )

    if (
        intent.settlement_source
        != PaymentIntent.SETTLEMENT_SUI
    ):
        raise SuiPaymentQuoteError(
            "PaymentIntent is not configured "
            "for SUI settlement."
        )

    try:
        item = FounderCartItem.objects.get(
            payment_intent=intent
        )
    except FounderCartItem.DoesNotExist as exc:
        raise SuiPaymentQuoteError(
            "SUI Founder payment has no cart item."
        ) from exc

    if (
        item.payment_method
        != FounderCartItem.PAYMENT_SUI
    ):
        raise SuiPaymentQuoteError(
            "Founder reservation is not "
            "a SUI purchase."
        )

    metadata = dict(
        intent.metadata or {}
    )

    # Reuse an already-frozen quote. Never silently
    # change an amount while the buyer may be paying it.
    if (
        metadata.get("sui_required_mist")
        and metadata.get(
            "sui_recipient_address"
        )
        and metadata.get(
            "sui_quote_expires_at"
        )
    ):
        return intent, False

    try:
        amount_usd = Decimal(
            str(intent.amount)
        )
    except InvalidOperation as exc:
        raise SuiPaymentQuoteError(
            "PaymentIntent has invalid USD amount."
        ) from exc

    if amount_usd <= 0:
        raise SuiPaymentQuoteError(
            "PaymentIntent amount must be positive."
        )

    try:
        response = quote_sui_payment(
            amount_usd=amount_usd,
        )
    except SuiAdapterError as exc:
        raise SuiPaymentQuoteError(
            "Unable to obtain SUI payment quote."
        ) from exc

    quote = response.get("quote")

    if not isinstance(quote, dict):
        raise SuiPaymentQuoteError(
            "Sui service returned no payment quote."
        )

    if quote.get("network") != "mainnet":
        raise SuiPaymentQuoteError(
            "SUI quote is not for mainnet."
        )

    recipient = str(
        quote.get(
            "recipient_address",
            "",
        )
    ).strip().lower()

    if not recipient:
        raise SuiPaymentQuoteError(
            "SUI quote has no recipient address."
        )

    try:
        required_mist = int(
            quote.get(
                "amount_mist",
                "0",
            )
        )
    except (TypeError, ValueError) as exc:
        raise SuiPaymentQuoteError(
            "SUI quote has invalid MIST amount."
        ) from exc

    if required_mist <= 0:
        raise SuiPaymentQuoteError(
            "SUI quote amount must be positive."
        )

    quote_expires_at = str(
        quote.get(
            "quote_expires_at",
            "",
        )
    ).strip()

    _parse_quote_datetime(
        quote_expires_at
    )

    metadata.update({
        "sui_network":
            "mainnet",
        "sui_recipient_address":
            recipient,
        "sui_required_mist":
            str(required_mist),
        "sui_amount":
            str(
                quote.get(
                    "amount_sui",
                    "",
                )
            ),
        "sui_usd_price":
            str(
                quote.get(
                    "sui_usd_price",
                    "",
                )
            ),
        "sui_quoted_at":
            str(
                quote.get(
                    "quoted_at",
                    "",
                )
            ),
        "sui_quote_expires_at":
            quote_expires_at,
    })

    intent.metadata = metadata

    intent.save(
        update_fields=[
            "metadata",
            "updated_at",
        ]
    )

    return intent, True
