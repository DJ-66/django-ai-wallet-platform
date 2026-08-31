"""
FANZ Sui starter-grant eligibility.

Important distinction:

- A Sui address controls whether Sui assets can be delivered.
- The payment rail controls whether FANZ may grant real SUI.

FANZ Credits NEVER qualify for the 0.25 SUI starter grant.
This prevents internal-credit activity from being converted into
subsidized external SUI.
"""

SUI_STARTER_GRANT_MIST = 250_000_000

STARTER_GRANT_PAYMENT_METHODS = frozenset(
    {
        "btc",
        "doge",
        "sui",
    }
)


def normalize_payment_method(value):
    return str(value or "").strip().lower()


def qualifies_for_sui_starter_grant(
    *,
    payment_method,
):
    """
    Return True only when a purchase was funded by an approved
    external payment rail.

    FANZ Credits intentionally never qualify.
    """
    return (
        normalize_payment_method(payment_method)
        in STARTER_GRANT_PAYMENT_METHODS
    )


def can_deliver_sui_assets(
    *,
    sui_address,
):
    """
    A Sui address is a delivery requirement only.

    It does not imply starter-grant eligibility.
    """
    return bool(
        str(sui_address or "").strip()
    )


def starter_grant_is_ready(
    *,
    payment_method,
    sui_address,
):
    """
    Ready means BOTH:

    1. Purchase funding qualifies.
    2. A Sui recipient address exists.

    A missing address should defer delivery, never block purchase.
    """
    return (
        qualifies_for_sui_starter_grant(
            payment_method=payment_method,
        )
        and can_deliver_sui_assets(
            sui_address=sui_address,
        )
    )
