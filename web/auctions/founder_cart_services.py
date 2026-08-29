from django.core.exceptions import ValidationError
from django.db import transaction

from .founder_vending import (
    founder_budget_quote,
    founder_coin_identity,
)
from .models import (
    FounderCart,
    FounderCartItem,
    FounderListing,
)


class FounderCartError(RuntimeError):
    pass


def _active_listing_for_handle(handle):
    return (
        FounderListing.objects
        .select_related("founder_account")
        .filter(
            founder_account__handle=handle,
            status=FounderListing.STATUS_ACTIVE,
        )
        .first()
    )


@transaction.atomic
def get_or_create_open_founder_cart(purchaser):
    cart = (
        FounderCart.objects
        .select_for_update()
        .filter(
            purchaser=purchaser,
            status=FounderCart.STATUS_OPEN,
        )
        .order_by("-created_at")
        .first()
    )

    if cart:
        return cart, False

    return (
        FounderCart.objects.create(
            purchaser=purchaser,
        ),
        True,
    )


@transaction.atomic
def add_founder_cart_item(
    *,
    purchaser,
    wanted_handle,
    budget_credits,
    purchase_mode=FounderCartItem.MODE_SELF,
    sui_recipient_address="",
    gift_recipient_name="",
    gift_recipient_email="",
    gift_message="",
):
    identity = founder_coin_identity(
        wanted_handle
    )

    quote = founder_budget_quote(
        budget_credits
    )

    cart, _ = get_or_create_open_founder_cart(
        purchaser
    )

    if cart.items.filter(
        wanted_handle=identity.handle
    ).exists():
        raise FounderCartError(
            f"@{identity.handle} is already in this cart."
        )

    listing = _active_listing_for_handle(
        identity.handle
    )

    if quote.suggest_swamp:
        status = (
            FounderCartItem.STATUS_SWAMP_SUGGESTED
        )
        list_price = None

    elif listing is None:
        # Valid Founder request, but no currently saleable
        # listing has been resolved yet.
        status = FounderCartItem.STATUS_PENDING
        list_price = quote.list_price_credits

    else:
        status = FounderCartItem.STATUS_AVAILABLE
        list_price = quote.list_price_credits

    item = FounderCartItem(
        cart=cart,
        wanted_handle=identity.handle,
        budget_credits=quote.budget_credits,
        list_price_credits=list_price,
        purchase_mode=purchase_mode,
        sui_recipient_address=(
            sui_recipient_address or ""
        ).strip(),
        gift_recipient_name=(
            gift_recipient_name or ""
        ).strip(),
        gift_recipient_email=(
            gift_recipient_email or ""
        ).strip(),
        gift_message=(
            gift_message or ""
        ).strip(),
        status=status,
    )

    try:
        item.full_clean()
    except ValidationError as exc:
        raise FounderCartError(
            str(exc)
        ) from exc

    item.save()

    return {
        "cart": cart,
        "item": item,
        "identity": identity,
        "quote": quote,
        "listing": listing,
    }
