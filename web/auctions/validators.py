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
