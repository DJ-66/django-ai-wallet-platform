from django.db import transaction
from django.utils import timezone

from .models import (
    FounderCartItem,
    PaymentIntent,
)
from .sui_adapter import (
    SuiAdapterError,
    verify_sui_payment,
)


class SuiPaymentSettlementError(RuntimeError):
    pass


@transaction.atomic
def settle_founder_sui_payment(
    *,
    payment_intent_id,
    tx_digest,
    recipient_address,
    minimum_amount_mist,
):
    """
    Verify one mainnet SUI payment and settle its
    Founder PaymentIntent.

    Verification is delegated to the FANZ Sui service.
    Django accepts settlement only when the returned
    transaction exactly matches this request.
    """

    intent = (
        PaymentIntent.objects
        .select_for_update()
        .select_related("user")
        .get(pk=payment_intent_id)
    )

    if intent.purpose != "founder_purchase":
        raise SuiPaymentSettlementError(
            "PaymentIntent is not a Founder purchase."
        )

    if (
        intent.settlement_source
        != PaymentIntent.SETTLEMENT_SUI
    ):
        raise SuiPaymentSettlementError(
            "PaymentIntent is not configured "
            "for SUI settlement."
        )

    try:
        item = FounderCartItem.objects.get(
            payment_intent=intent
        )
    except FounderCartItem.DoesNotExist as exc:
        raise SuiPaymentSettlementError(
            "SUI Founder payment has no cart item."
        ) from exc

    if (
        item.payment_method
        != FounderCartItem.PAYMENT_SUI
    ):
        raise SuiPaymentSettlementError(
            "Founder reservation is not a SUI purchase."
        )

    digest = str(tx_digest or "").strip()
    recipient = str(
        recipient_address or ""
    ).strip().lower()

    minimum_mist = int(
        minimum_amount_mist
    )

    if not digest:
        raise SuiPaymentSettlementError(
            "SUI transaction digest is required."
        )

    if minimum_mist <= 0:
        raise SuiPaymentSettlementError(
            "SUI payment amount must be positive."
        )

    # Idempotent retry of the same accepted transaction.
    if intent.status in {
        "settled",
        "fulfilled",
    }:
        if intent.settlement_reference != digest:
            raise SuiPaymentSettlementError(
                "PaymentIntent is already settled "
                "with another SUI transaction."
            )

        return intent, False

    if intent.status not in {
        "created",
        "invoice_created",
        "processing",
    }:
        raise SuiPaymentSettlementError(
            "PaymentIntent cannot accept SUI settlement "
            f"from status {intent.status}."
        )

    try:
        response = verify_sui_payment(
            tx_digest=digest,
            recipient_address=recipient,
            minimum_amount_mist=minimum_mist,
        )
    except SuiAdapterError as exc:
        raise SuiPaymentSettlementError(
            "Unable to verify SUI payment."
        ) from exc

    verification = response.get(
        "verification"
    )

    if not isinstance(verification, dict):
        raise SuiPaymentSettlementError(
            "Sui verifier returned no verification."
        )

    if verification.get("network") != "mainnet":
        raise SuiPaymentSettlementError(
            "SUI payment was not verified on mainnet."
        )

    if verification.get("tx_digest") != digest:
        raise SuiPaymentSettlementError(
            "SUI transaction digest mismatch."
        )

    if (
        str(
            verification.get(
                "recipient_address",
                "",
            )
        ).strip().lower()
        != recipient
    ):
        raise SuiPaymentSettlementError(
            "SUI payment recipient mismatch."
        )

    if verification.get("success") is not True:
        raise SuiPaymentSettlementError(
            "SUI transaction was not successful."
        )

    if verification.get("sufficient") is not True:
        raise SuiPaymentSettlementError(
            "SUI payment amount is insufficient."
        )

    try:
        received_mist = int(
            verification.get(
                "received_mist",
                "0",
            )
        )
    except (TypeError, ValueError) as exc:
        raise SuiPaymentSettlementError(
            "SUI verifier returned invalid amount."
        ) from exc

    if received_mist < minimum_mist:
        raise SuiPaymentSettlementError(
            "SUI payment amount is below minimum."
        )

    intent.settlement_reference = digest
    intent.status = "settled"

    if intent.paid_at is None:
        intent.paid_at = timezone.now()

    intent.save(
        update_fields=[
            "settlement_reference",
            "status",
            "paid_at",
            "updated_at",
        ]
    )

    return intent, True
