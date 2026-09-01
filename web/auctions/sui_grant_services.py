from .sui_adapter import (
    create_sui_starter_grant,
)
from .sui_grant_policy import (
    SUI_STARTER_GRANT_MIST,
    starter_grant_is_ready,
)


class SuiStarterGrantError(RuntimeError):
    pass


def starter_grant_submission_key(
    *,
    payment_intent_id,
):
    return (
        "starter-grant-payment-intent-"
        f"{int(payment_intent_id)}"
    )


def grant_starter_sui_for_payment_intent(
    *,
    payment_intent,
    payment_method,
    sui_address,
):
    """
    Attempt the fixed FANZ starter grant.

    Missing Sui address defers delivery.
    FANZ Credits never qualify.
    """

    ready = starter_grant_is_ready(
        payment_method=payment_method,
        sui_address=sui_address,
    )

    if not ready:
        return {
            "delivered": False,
            "deferred": True,
        }

    if payment_intent.pk is None:
        raise SuiStarterGrantError(
            "Starter grant requires a saved PaymentIntent."
        )

    if payment_intent.status not in {
        "settled",
        "fulfilled",
    }:
        raise SuiStarterGrantError(
            "Starter grant requires settled payment."
        )

    submission_key = (
        starter_grant_submission_key(
            payment_intent_id=payment_intent.pk,
        )
    )

    response = create_sui_starter_grant(
        submission_key=submission_key,
        recipient_address=sui_address,
    )

    transfer = response.get("transfer")

    if not isinstance(transfer, dict):
        raise SuiStarterGrantError(
            "Sui service returned no starter transfer."
        )

    if (
        transfer.get("submission_key")
        != submission_key
    ):
        raise SuiStarterGrantError(
            "Starter grant submission key mismatch."
        )

    if (
        str(transfer.get("amount_mist"))
        != str(SUI_STARTER_GRANT_MIST)
    ):
        raise SuiStarterGrantError(
            "Starter grant amount mismatch."
        )

    if transfer.get("state") != "confirmed":
        raise SuiStarterGrantError(
            "Starter grant was not confirmed."
        )

    return {
        "delivered": True,
        "deferred": False,
        "submission_key": submission_key,
        "tx_digest": transfer.get("tx_digest"),
    }
