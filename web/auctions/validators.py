from django.core.exceptions import ValidationError

RESERVED_USERNAMES = {
    "admin", "accounts", "login", "logout", "signup",
    "auctions", "feed", "wallet", "api", "static", "media",
    "support", "billing", "notifications", "noreply",
    "about", "terms", "privacy", "contact", "help",
    "u", "user", "users", "creator", "creators",
}

def validate_username_not_reserved(value):
    if value.lower() in RESERVED_USERNAMES:
        raise ValidationError("This username is reserved. Please choose another.")

FOUNDER_ALLOWED_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789.+-_"
)

FOUNDER_MIN_LENGTH = 1
FOUNDER_MAX_LENGTH = 4
FOUNDER_FLOOR_CREDITS = 200


def normalize_founder_handle(value):
    """
    Return the canonical FANZ Founder handle.

    Founder handles are case-insensitive and stored canonically
    in lowercase. The leading @ is display syntax and is not part
    of the Founder property itself.
    """
    if value is None:
        return ""

    value = str(value).strip()

    if value.startswith("@"):
        value = value[1:]

    return value.lower()


def validate_founder_handle(value):
    """
    Validate one canonical FANZ Founder property address.

    Valid Founder handles:
    - contain 1-4 characters
    - use only the permanent FANZ Founder alphabet
    - do not include @ as part of the stored handle
    """
    handle = normalize_founder_handle(value)

    if not (
        FOUNDER_MIN_LENGTH
        <= len(handle)
        <= FOUNDER_MAX_LENGTH
    ):
        raise ValidationError(
            "Founder handles must contain between 1 and 4 characters."
        )

    invalid_chars = sorted(
        set(handle) - FOUNDER_ALLOWED_CHARS
    )

    if invalid_chars:
        raise ValidationError(
            "Founder handle contains unsupported characters: "
            + " ".join(invalid_chars)
        )

    return handle


def is_valid_founder_handle(value):
    try:
        validate_founder_handle(value)
    except ValidationError:
        return False

    return True
