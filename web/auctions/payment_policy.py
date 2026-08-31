"""
Central FANZ payment-rail policy.

Platform commerce may accept:
    FANZ Credits
    BTC
    DOGE
    SUI

User-to-user economy paths that must remain inside the
FANZ Credits economy accept Credits only.
"""

PAYMENT_CREDITS = "credits"
PAYMENT_BTC = "btc"
PAYMENT_DOGE = "doge"
PAYMENT_SUI = "sui"

PAYMENT_METHODS = frozenset({
    PAYMENT_CREDITS,
    PAYMENT_BTC,
    PAYMENT_DOGE,
    PAYMENT_SUI,
})

PLATFORM_PAYMENT_METHODS = frozenset({
    PAYMENT_CREDITS,
    PAYMENT_BTC,
    PAYMENT_DOGE,
    PAYMENT_SUI,
})

CREDITS_ONLY_PAYMENT_METHODS = frozenset({
    PAYMENT_CREDITS,
})


CONTEXT_PLATFORM_FOUNDER = "platform_founder"
CONTEXT_PLATFORM_CREDIT_SALE = "platform_credit_sale"
CONTEXT_PLATFORM_MEME_COIN = "platform_meme_coin"
CONTEXT_PLATFORM_DONATION = "platform_donation"
CONTEXT_PLATFORM_CROWDFUNDING = "platform_crowdfunding"
CONTEXT_PLATFORM_SERVICE = "platform_service"

CONTEXT_FOUNDER_P2P = "founder_p2p"
CONTEXT_FEED_TIP = "feed_tip"
CONTEXT_POST_UNLOCK = "post_unlock"


PLATFORM_COMMERCE_CONTEXTS = frozenset({
    CONTEXT_PLATFORM_FOUNDER,
    CONTEXT_PLATFORM_CREDIT_SALE,
    CONTEXT_PLATFORM_MEME_COIN,
    CONTEXT_PLATFORM_DONATION,
    CONTEXT_PLATFORM_CROWDFUNDING,
    CONTEXT_PLATFORM_SERVICE,
})


CREDITS_ONLY_CONTEXTS = frozenset({
    CONTEXT_FOUNDER_P2P,
    CONTEXT_FEED_TIP,
    CONTEXT_POST_UNLOCK,
})


def normalize_payment_method(value):
    return str(value or "").strip().lower()


def allowed_payment_methods(
    *,
    context,
    seller_is_platform=False,
):
    """
    Return payment rails allowed for one FANZ transaction.

    Non-platform P2P Founder sales, feed tips, and paid-post
    unlocks remain FANZ Credits-only.

    Platform commerce may use Credits, BTC, DOGE, or SUI.
    """

    context = str(context or "").strip().lower()

    if context in {
        CONTEXT_FEED_TIP,
        CONTEXT_POST_UNLOCK,
    }:
        return CREDITS_ONLY_PAYMENT_METHODS

    if context == CONTEXT_FOUNDER_P2P:
        if seller_is_platform:
            return PLATFORM_PAYMENT_METHODS

        return CREDITS_ONLY_PAYMENT_METHODS

    if context in PLATFORM_COMMERCE_CONTEXTS:
        return PLATFORM_PAYMENT_METHODS

    # Unknown contexts fail closed.
    return CREDITS_ONLY_PAYMENT_METHODS


def payment_method_allowed(
    *,
    context,
    payment_method,
    seller_is_platform=False,
):
    return (
        normalize_payment_method(payment_method)
        in allowed_payment_methods(
            context=context,
            seller_is_platform=seller_is_platform,
        )
    )
