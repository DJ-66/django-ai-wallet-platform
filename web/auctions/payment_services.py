from django.db import transaction
from django.utils import timezone

from .models import PaymentIntent
from .services import process_credit_purchase


class PaymentFulfillmentError(RuntimeError):
    pass


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

    if not intent.btcpay_invoice_id:
        raise PaymentFulfillmentError(
            "PaymentIntent has no BTCPay invoice id."
        )

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

    elif intent.purpose == "donation":
        # Settlement itself is the fulfillment for a donation.
        # Donations deliberately mint no FANZ Credits.
        pass

    elif intent.purpose == "integration_test":
        # Integration tests deliberately have no economic fulfillment.
        pass

    else:
        raise PaymentFulfillmentError(
            f"No fulfillment handler for purpose: {intent.purpose}"
        )

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
