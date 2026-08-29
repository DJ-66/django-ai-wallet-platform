from django.core.exceptions import ValidationError
from django.db import transaction
from datetime import timedelta
from django.utils import timezone
from .founder_vending import (
    founder_budget_quote,
    founder_coin_identity,
)
from .models import (
    BidWallet,
    FounderAccount,
    FounderCart,
    FounderCartItem,
    FounderListing,
    FounderOwnershipLedger,
    FounderPriceMemory,
    FounderVendingHold,
    WalletTransaction,
)
from .founder_services import normalize_owner_root
from .founder_ledger import append_founder_ownership_ledger


FOUNDER_RESERVATION_TTL = timedelta(hours=1)
FOUNDER_PRICE_MEMORY_TTL = timedelta(hours=4)
from .utils import get_system_wallet

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
def create_founder_vending_reservation(
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
    buyer_root = normalize_owner_root(purchaser)

    identity = founder_coin_identity(
        wanted_handle
    )

    quote = founder_budget_quote(
        budget_credits
    )

    if quote.suggest_swamp:
        raise FounderCartError(
            "Budget does not qualify for a custom Founder reservation."
        )

    budget = quote.budget_credits
    proposed_list_price = quote.list_price_credits

    now = timezone.now()

    memory = (
        FounderPriceMemory.objects
        .select_for_update()
        .filter(
            buyer_root=buyer_root,
            wanted_handle=identity.handle,
        )
        .first()
    )

    if memory and memory.expires_at <= now:
        memory.delete()
        memory = None

    if memory:
        effective_list_price = (
            memory.list_price_credits
        )

        if budget < effective_list_price:
            raise FounderCartError(
                "Budget is below the active List Price "
                "for this Founder handle."
            )
    else:
        effective_list_price = proposed_list_price

    wallet = (
        BidWallet.objects
        .select_for_update()
        .filter(user=buyer_root)
        .first()
    )

    if wallet is None:
        raise FounderCartError(
            "Buyer has no FANZ credit wallet."
        )

    if wallet.credits < budget:
        raise FounderCartError(
            "Available FANZ credits are below the submitted budget."
        )

    cart, _ = get_or_create_open_founder_cart(
        purchaser
    )

    existing = (
        cart.items
        .select_for_update()
        .filter(
            wanted_handle=identity.handle
        )
        .first()
    )

    if existing is not None:
        raise FounderCartError(
            f"@{identity.handle} is already in this cart."
        )

    active_other_reservation = (
        FounderCartItem.objects
        .select_for_update()
        .filter(
            wanted_handle=identity.handle,
            status=FounderCartItem.STATUS_QUOTED,
            reservation_expires_at__gt=now,
        )
        .exclude(
            cart__purchaser=purchaser
        )
        .first()
    )

    if active_other_reservation is not None:
        raise FounderCartError(
            f"@{identity.handle} is temporarily reserved."
        )

    founder = (
        FounderAccount.objects
        .select_for_update()
        .filter(
            handle=identity.handle,
        )
        .first()
    )

    if founder is not None:
        if founder.owner_root_id is not None:
            raise FounderCartError(
                f"@{identity.handle} is already owned."
            )

        if founder.status not in {
            FounderAccount.STATUS_AVAILABLE,
            FounderAccount.STATUS_TREASURY,
            FounderAccount.STATUS_RESERVED,
        }:
            raise FounderCartError(
                f"@{identity.handle} is not available "
                "for vending."
            )

    reservation_expires_at = (
        now + FOUNDER_RESERVATION_TTL
    )

    if memory:
        price_memory_expires_at = memory.expires_at
    else:
        price_memory_expires_at = (
            now + FOUNDER_PRICE_MEMORY_TTL
        )

    item = FounderCartItem(
        cart=cart,
        wanted_handle=identity.handle,
        budget_credits=budget,
        list_price_credits=effective_list_price,
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
        status=FounderCartItem.STATUS_QUOTED,
        quoted_at=now,
        reservation_expires_at=(
            reservation_expires_at
        ),
        price_memory_expires_at=(
            price_memory_expires_at
        ),
    )

    try:
        item.full_clean()
    except ValidationError as exc:
        raise FounderCartError(
            str(exc)
        ) from exc

    wallet.credits -= budget
    wallet.save(
        update_fields=["credits"]
    )

    item.save()

    if founder is None:
        founder = FounderAccount.objects.create(
            handle=identity.handle,
            status=FounderAccount.STATUS_RESERVED,
        )
    else:
        founder.status = FounderAccount.STATUS_RESERVED
        founder.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    hold = FounderVendingHold.objects.create(
        cart_item=item,
        wallet=wallet,
        amount_credits=budget,
        status=FounderVendingHold.STATUS_HELD,
    )

    if memory is None:
        memory = FounderPriceMemory.objects.create(
            buyer_root=buyer_root,
            wanted_handle=identity.handle,
            list_price_credits=(
                effective_list_price
            ),
            expires_at=(
                price_memory_expires_at
            ),
        )

    return {
        "cart": cart,
        "item": item,
        "hold": hold,
        "memory": memory,
        "identity": identity,
        "buyer_root": buyer_root,
        "founder_account": founder,
    }


def _release_vending_hold(*, item, final_status):
    hold = (
        FounderVendingHold.objects
        .select_for_update()
        .select_related("wallet")
        .filter(
            cart_item=item,
        )
        .first()
    )

    if hold is None:
        raise FounderCartError(
            "Founder reservation has no credit hold."
        )

    if hold.status == FounderVendingHold.STATUS_RELEASED:
        if item.status != final_status:
            item.status = final_status
            item.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        return hold, False

    if hold.status != FounderVendingHold.STATUS_HELD:
        raise FounderCartError(
            "Founder reservation credit hold "
            "cannot be released."
        )

    wallet = (
        BidWallet.objects
        .select_for_update()
        .get(pk=hold.wallet_id)
    )

    wallet.credits += hold.amount_credits
    wallet.save(
        update_fields=["credits"]
    )

    hold.status = FounderVendingHold.STATUS_RELEASED
    hold.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    item.status = final_status
    item.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    founder = (
        FounderAccount.objects
        .select_for_update()
        .filter(
            handle=item.wanted_handle,
            status=FounderAccount.STATUS_RESERVED,
            owner_root__isnull=True,
        )
        .first()
    )

    if founder is not None:
        founder.status = FounderAccount.STATUS_AVAILABLE
        founder.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    return hold, True


@transaction.atomic
def cancel_founder_vending_reservation(
    *,
    purchaser,
    cart_item_id,
):
    buyer_root = normalize_owner_root(purchaser)

    item = (
        FounderCartItem.objects
        .select_for_update()
        .select_related("cart__purchaser")
        .get(pk=cart_item_id)
    )

    item_buyer_root = normalize_owner_root(
        item.cart.purchaser
    )

    if item_buyer_root.pk != buyer_root.pk:
        raise FounderCartError(
            "Founder reservation does not belong "
            "to this buyer."
        )

    if item.status == FounderCartItem.STATUS_PURCHASED:
        raise FounderCartError(
            "Purchased Founder reservations "
            "cannot be cancelled."
        )

    if item.status == FounderCartItem.STATUS_EXPIRED:
        return item, False

    if item.status == FounderCartItem.STATUS_CANCELLED:
        return item, False

    if item.status != FounderCartItem.STATUS_QUOTED:
        raise FounderCartError(
            "Only quoted Founder reservations "
            "can be cancelled."
        )

    _release_vending_hold(
        item=item,
        final_status=FounderCartItem.STATUS_CANCELLED,
    )

    return item, True


@transaction.atomic
def expire_founder_vending_reservations(
    *,
    now=None,
):
    now = now or timezone.now()

    item_ids = list(
        FounderCartItem.objects
        .filter(
            status=FounderCartItem.STATUS_QUOTED,
            reservation_expires_at__lte=now,
        )
        .values_list("pk", flat=True)
    )

    expired_count = 0

    for item_id in item_ids:
        item = (
            FounderCartItem.objects
            .select_for_update()
            .get(pk=item_id)
        )

        # Recheck after obtaining the row lock.
        if item.status != FounderCartItem.STATUS_QUOTED:
            continue

        if (
            item.reservation_expires_at is None
            or item.reservation_expires_at > now
        ):
            continue

        _release_vending_hold(
            item=item,
            final_status=FounderCartItem.STATUS_EXPIRED,
        )

        expired_count += 1

    return expired_count

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


@transaction.atomic
def purchase_founder_vending_reservation(
    *,
    purchaser,
    cart_item_id,
    now=None,
):
    now = now or timezone.now()
    buyer_root = normalize_owner_root(purchaser)

    item = (
        FounderCartItem.objects
        .select_for_update()
        .select_related("cart__purchaser")
        .get(pk=cart_item_id)
    )

    item_buyer_root = normalize_owner_root(
        item.cart.purchaser
    )

    if item_buyer_root.pk != buyer_root.pk:
        raise FounderCartError(
            "Founder reservation does not belong "
            "to this buyer."
        )

    if item.status == FounderCartItem.STATUS_PURCHASED:
        return {
            "purchased": False,
            "already_purchased": True,
            "expired": False,
            "item": item,
        }

    if item.status != FounderCartItem.STATUS_QUOTED:
        raise FounderCartError(
            "Founder reservation is not purchasable."
        )

    if (
        item.reservation_expires_at is None
        or item.reservation_expires_at <= now
    ):
        _release_vending_hold(
            item=item,
            final_status=FounderCartItem.STATUS_EXPIRED,
        )

        return {
            "purchased": False,
            "already_purchased": False,
            "expired": True,
            "item": item,
        }

    hold = (
        FounderVendingHold.objects
        .select_for_update()
        .get(cart_item=item)
    )

    if hold.status != FounderVendingHold.STATUS_HELD:
        raise FounderCartError(
            "Founder reservation funds are not held."
        )

    list_price = int(
        item.list_price_credits or 0
    )

    if list_price < 200:
        raise FounderCartError(
            "Founder List Price is invalid."
        )

    if hold.amount_credits < list_price:
        raise FounderCartError(
            "Founder reservation hold is below "
            "the List Price."
        )

    founder = (
        FounderAccount.objects
        .select_for_update()
        .get(handle=item.wanted_handle)
    )

    if founder.status != FounderAccount.STATUS_RESERVED:
        raise FounderCartError(
            f"@{founder.handle} is no longer reserved."
        )

    if founder.owner_root_id is not None:
        raise FounderCartError(
            f"@{founder.handle} is already owned."
        )

    system_wallet = get_system_wallet()
    platform_user = system_wallet.user

    if buyer_root.pk == platform_user.pk:
        raise FounderCartError(
            "The FANZ platform cannot purchase "
            "Founder vending inventory."
        )

    wallet_ids = sorted({
        hold.wallet_id,
        system_wallet.pk,
    })

    locked_wallets = {
        wallet.pk: wallet
        for wallet in (
            BidWallet.objects
            .select_for_update()
            .filter(pk__in=wallet_ids)
            .order_by("pk")
        )
    }

    buyer_wallet = locked_wallets.get(
        hold.wallet_id
    )

    platform_wallet = locked_wallets.get(
        system_wallet.pk
    )

    if buyer_wallet is None:
        raise FounderCartError(
            "Reserved buyer wallet could not be locked."
        )

    if platform_wallet is None:
        raise FounderCartError(
            "FANZ platform wallet could not be locked."
        )

    if buyer_wallet.user_id != buyer_root.pk:
        raise FounderCartError(
            "Founder hold does not belong "
            "to the authoritative buyer wallet."
        )

    refund_credits = (
        hold.amount_credits - list_price
    )

    # Full Budget was removed when the reservation
    # was created. Never debit the buyer again.
    platform_wallet.credits += list_price

    if refund_credits:
        buyer_wallet.credits += refund_credits

    platform_wallet.save(
        update_fields=["credits"]
    )

    if refund_credits:
        buyer_wallet.save(
            update_fields=["credits"]
        )

    purchase_tx = WalletTransaction.objects.create(
        sender=buyer_wallet,
        receiver=platform_wallet,
        amount=list_price,
        transaction_type="purchase",
        reference=(
            f"Founder vending purchase "
            f"@{founder.handle}: "
            f"budget={hold.amount_credits}; "
            f"price={list_price}; "
            f"refund={refund_credits}"
        ),
    )

    founder.owner_root = buyer_root
    founder.status = FounderAccount.STATUS_OWNED

    founder.save(
        update_fields=[
            "owner_root",
            "status",
            "updated_at",
        ]
    )

    ledger_record = append_founder_ownership_ledger(
        founder_account=founder,
        seller_root=platform_user,
        buyer_root=buyer_root,
        transfer_type=(
            FounderOwnershipLedger
            .TRANSFER_TREASURY_RELEASE
        ),
        sale_price_credits=list_price,
        platform_fee_credits=0,
        seller_proceeds_credits=list_price,
        wallet_transaction_ids=[
            purchase_tx.pk,
        ],
        metadata_snapshot={
            "seller_username":
                platform_user.username,
            "buyer_username":
                buyer_root.username,
            "handle":
                founder.handle,
            "vending":
                True,
            "cart_item_id":
                item.pk,
            "budget_credits":
                hold.amount_credits,
            "refund_credits":
                refund_credits,
        },
    )

    hold.status = (
        FounderVendingHold.STATUS_CONSUMED
    )

    hold.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    item.status = FounderCartItem.STATUS_PURCHASED

    item.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return {
        "purchased": True,
        "already_purchased": False,
        "expired": False,
        "item": item,
        "hold": hold,
        "founder_account": founder,
        "buyer_root": buyer_root,
        "platform_wallet": platform_wallet,
        "sale_price_credits": list_price,
        "refund_credits": refund_credits,
        "wallet_transaction": purchase_tx,
        "ledger_record": ledger_record,
    }
