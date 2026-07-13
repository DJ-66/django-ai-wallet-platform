EVENT_CREDIT_THRESHOLD = 1000


def can_create_events(user):
    if not user or not user.is_authenticated:
        return False

    wallet = getattr(user, "bidwallet", None)

    return bool(
        wallet
        and wallet.credits >= EVENT_CREDIT_THRESHOLD
    )
