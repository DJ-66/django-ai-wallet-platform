from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

from .founder_ledger import append_founder_ownership_ledger
from .models import (
    AccountControl,
    BidWallet,
    FounderListing,
    FounderAccount,
    FounderOwnershipLedger,
    WalletTransaction,
    FounderBid,
    FounderCreditHold,
)
from .utils import get_system_wallet

FOUNDER_MIN_TRANSFER_CREDITS = 200
FOUNDER_PLATFORM_FEE_RATE = Decimal("0.15")


@transaction.atomic
def transfer_founder_ownership(
    *,
    founder_account,
    buyer,
    sale_price_credits,
):
    """
    Atomically transfer a Founder property between independent roots.

    Rules:
    - minimum recognized external conveyance: 200 credits
    - buyer and seller must resolve to different authoritative roots
    - buyer must have sufficient credits
    - Founder asset and all settlement wallets are row-locked
    - 15% FANZ fee settles to the canonical @platform wallet
    - ownership changes only after financial validation succeeds
    """

    sale_price_credits = int(sale_price_credits)

    if sale_price_credits < FOUNDER_MIN_TRANSFER_CREDITS:
        raise ValidationError(
            f"Founder ownership transfers require at least "
            f"{FOUNDER_MIN_TRANSFER_CREDITS} credits."
        )

    locked_asset = (
        FounderAccount.objects
        .select_for_update()
        .get(pk=founder_account.pk)
    )

    if locked_asset.owner_root is None:
        raise ValidationError(
            "Founder property does not currently have an owner."
        )

    seller_root = get_authoritative_root(
        locked_asset.owner_root
    )
    buyer_root = get_authoritative_root(
        buyer
    )

    if seller_root.pk == buyer_root.pk:
        raise ValidationError(
            "Internal same-root movement is not an external Founder sale."
        )

    # Resolve the canonical FANZ system wallet, then lock the
    # authoritative wallet row participating in this settlement.
    system_wallet = get_system_wallet()

    wallet_ids = sorted({
        BidWallet.objects.get(user=buyer_root).pk,
        BidWallet.objects.get(user=seller_root).pk,
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

    buyer_wallet = locked_wallets[
        BidWallet.objects.get(user=buyer_root).pk
    ]

    seller_wallet = locked_wallets[
        BidWallet.objects.get(user=seller_root).pk
    ]

    platform_wallet = locked_wallets[
        system_wallet.pk
    ]

    if buyer_wallet.pk == platform_wallet.pk:
        raise ValidationError(
            "The FANZ platform wallet cannot purchase Founder property "
            "through the normal P2P sale path."
        )

    if seller_wallet.pk == platform_wallet.pk:
        raise ValidationError(
            "FANZ Treasury sales require the Treasury sale path."
        )

    if buyer_wallet.credits < sale_price_credits:
        raise ValidationError(
            "Buyer does not have enough credits."
        )

    platform_fee = int(
        Decimal(sale_price_credits)
        * FOUNDER_PLATFORM_FEE_RATE
    )

    seller_proceeds = (
        sale_price_credits - platform_fee
    )

    buyer_wallet.credits -= sale_price_credits
    seller_wallet.credits += seller_proceeds
    platform_wallet.credits += platform_fee

    buyer_wallet.save(update_fields=["credits"])
    seller_wallet.save(update_fields=["credits"])
    platform_wallet.save(update_fields=["credits"])

    seller_tx = WalletTransaction.objects.create(
        sender=buyer_wallet,
        receiver=seller_wallet,
        amount=seller_proceeds,
        transaction_type="transfer",
        reference=(
            f"Founder sale @{locked_asset.handle}: "
            f"gross={sale_price_credits}; "
            f"seller={seller_proceeds}"
        ),
    )

    platform_tx = WalletTransaction.objects.create(
        sender=buyer_wallet,
        receiver=platform_wallet,
        amount=platform_fee,
        transaction_type="transfer",
        reference=(
            f"Founder platform fee @{locked_asset.handle}: "
            f"gross={sale_price_credits}; "
            f"fee={platform_fee}"
        ),
    )

    locked_asset.owner_root = buyer_root
    locked_asset.status = FounderAccount.STATUS_OWNED

    locked_asset.save(
        update_fields=[
            "owner_root",
            "status",
            "updated_at",
        ]
    )
    ledger_record = append_founder_ownership_ledger(
        founder_account=locked_asset,
        seller_root=seller_root,
        buyer_root=buyer_root,
        transfer_type=(
            FounderOwnershipLedger
            .TRANSFER_MINIMUM_CONVEYANCE
        ),
        sale_price_credits=sale_price_credits,
        platform_fee_credits=platform_fee,
        seller_proceeds_credits=seller_proceeds,
        wallet_transaction_ids=[
            seller_tx.pk,
            platform_tx.pk,
        ],
        metadata_snapshot={
            "seller_username": seller_root.username,
            "buyer_username": buyer_root.username,
            "handle": locked_asset.handle,
        },
    )

    return {
        "founder_account": locked_asset,
        "seller_root": seller_root,
        "buyer_root": buyer_root,
        "sale_price_credits": sale_price_credits,
        "platform_fee_credits": platform_fee,
        "seller_proceeds_credits": seller_proceeds,
        "ledger_record": ledger_record,
    }

@transaction.atomic
def purchase_tienda_fixed_listing(
    *,
    listing,
    buyer,
):
    """
    Atomically purchase a fixed-price Founder property from FANZ Tienda.

    Rules:
    - listing must be active Tienda inventory
    - listing must use fixed-price sale mode
    - authoritative listing price must be >= 200 credits
    - property must still be owned by FANZ Treasury/@platform
    - buyer must have sufficient credits
    - buyer wallet, platform wallet, listing, and property are locked
    - full sale price settles to @platform
    - title moves to buyer authoritative root
    - listing closes as sold
    - ownership ledger records a Treasury release
    """

    locked_listing = (
        FounderListing.objects
        .select_for_update()
        .get(pk=listing.pk)
    )

    if locked_listing.status != FounderListing.STATUS_ACTIVE:
        raise ValidationError(
            "Founder Tienda listing is no longer active."
        )

    if locked_listing.listing_source != FounderListing.SOURCE_TIENDA:
        raise ValidationError(
            "This listing is not FANZ Tienda inventory."
        )

    if locked_listing.sale_type != FounderListing.SALE_FIXED:
        raise ValidationError(
            "Blind-sale Tienda listings cannot use the fixed purchase path."
        )

    if locked_listing.starts_at > timezone.now():
        raise ValidationError(
            "Founder Tienda listing has not started yet."
        )

    sale_price_credits = int(
        locked_listing.fixed_price_credits or 0
    )

    if sale_price_credits < FOUNDER_MIN_TRANSFER_CREDITS:
        raise ValidationError(
            "Founder Tienda purchases require at least 200 credits."
        )

    locked_asset = (
        FounderAccount.objects
        .select_for_update()
        .get(pk=locked_listing.founder_account_id)
    )

    system_wallet = get_system_wallet()
    platform_user = system_wallet.user

    if locked_listing.seller_root_id != platform_user.pk:
        raise ValidationError(
            "Tienda listing seller is not the FANZ Treasury."
        )

    if locked_asset.owner_root_id != platform_user.pk:
        raise ValidationError(
            "Founder property is no longer owned by FANZ Treasury."
        )

    if locked_asset.status != FounderAccount.STATUS_LISTED:
        raise ValidationError(
            "Founder property is not currently listed."
        )

    buyer_root = get_authoritative_root(buyer)

    if buyer_root.pk == platform_user.pk:
        raise ValidationError(
            "The FANZ platform cannot buy its own Tienda inventory."
        )

    buyer_wallet_id = (
        BidWallet.objects
        .get(user=buyer_root)
        .pk
    )

    wallet_ids = sorted({
        buyer_wallet_id,
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

    buyer_wallet = locked_wallets[
        buyer_wallet_id
    ]

    platform_wallet = locked_wallets[
        system_wallet.pk
    ]

    if buyer_wallet.credits < sale_price_credits:
        raise ValidationError(
            "Buyer does not have enough credits."
        )

    buyer_wallet.credits -= sale_price_credits
    platform_wallet.credits += sale_price_credits

    buyer_wallet.save(
        update_fields=["credits"]
    )

    platform_wallet.save(
        update_fields=["credits"]
    )

    purchase_tx = WalletTransaction.objects.create(
        sender=buyer_wallet,
        receiver=platform_wallet,
        amount=sale_price_credits,
        transaction_type="purchase",
        reference=(
            f"Founder Tienda purchase @{locked_asset.handle}: "
            f"price={sale_price_credits}"
        ),
    )

    locked_asset.owner_root = buyer_root
    locked_asset.status = FounderAccount.STATUS_OWNED

    locked_asset.save(
        update_fields=[
            "owner_root",
            "status",
            "updated_at",
        ]
    )

    locked_listing.status = FounderListing.STATUS_SOLD

    locked_listing.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    ledger_record = append_founder_ownership_ledger(
        founder_account=locked_asset,
        seller_root=platform_user,
        buyer_root=buyer_root,
        transfer_type=(
            FounderOwnershipLedger
            .TRANSFER_TREASURY_RELEASE
        ),
        sale_price_credits=sale_price_credits,
        platform_fee_credits=0,
        seller_proceeds_credits=sale_price_credits,
        wallet_transaction_ids=[
            purchase_tx.pk,
        ],
        metadata_snapshot={
            "seller_username": platform_user.username,
            "buyer_username": buyer_root.username,
            "handle": locked_asset.handle,
            "listing_id": locked_listing.pk,
            "tienda_lane": locked_listing.tienda_lane,
        },
    )

    return {
        "listing": locked_listing,
        "founder_account": locked_asset,
        "buyer_root": buyer_root,
        "sale_price_credits": sale_price_credits,
        "platform_credits_received": sale_price_credits,
        "ledger_record": ledger_record,
    }

@transaction.atomic
def place_founder_blind_bid(
    *,
    listing,
    bidder,
    amount_credits,
):
    """
    Place or raise one fully funded bid on an active blind Founder listing.

    Held credits are removed from the bidder's spendable BidWallet balance.
    Raising an existing bid only reserves the additional difference.
    """

    amount_credits = int(amount_credits)

    if amount_credits < FOUNDER_MIN_TRANSFER_CREDITS:
        raise ValidationError(
            "Founder bids require at least 200 credits."
        )

    locked_listing = (
        FounderListing.objects
        .select_for_update()
        .get(pk=listing.pk)
    )

    if locked_listing.status != FounderListing.STATUS_ACTIVE:
        raise ValidationError(
            "Founder listing is no longer active."
        )

    if locked_listing.sale_type != FounderListing.SALE_BLIND:
        raise ValidationError(
            "This Founder listing does not accept blind bids."
        )

    now = timezone.now()

    if locked_listing.starts_at > now:
        raise ValidationError(
            "Founder blind sale has not started yet."
        )

    if locked_listing.ends_at is None or locked_listing.ends_at <= now:
        raise ValidationError(
            "Founder blind sale has already ended."
        )

    minimum_bid = int(
        locked_listing.minimum_bid_credits or 0
    )

    if amount_credits < minimum_bid:
        raise ValidationError(
            f"Bid must be at least {minimum_bid} credits."
        )

    bidder_root = get_authoritative_root(bidder)

    if bidder_root.pk == locked_listing.seller_root_id:
        raise ValidationError(
            "Seller cannot bid on their own Founder property."
        )
    

    bidder_wallet = (
        BidWallet.objects
        .select_for_update()
        .get(user=bidder_root)
    )

    existing_bid = (
        FounderBid.objects
        .select_for_update()
        .filter(
            listing=locked_listing,
            bidder_root=bidder_root,
            status=FounderBid.STATUS_ACTIVE,
        )
        .first()
    )

    if existing_bid is None:
        if bidder_wallet.credits < amount_credits:
            raise ValidationError(
                "Bidder does not have enough available credits."
            )

        bidder_wallet.credits -= amount_credits
        bidder_wallet.save(
            update_fields=["credits"]
        )

        bid = FounderBid.objects.create(
            listing=locked_listing,
            bidder_root=bidder_root,
            amount_credits=amount_credits,
            status=FounderBid.STATUS_ACTIVE,
        )

        hold = FounderCreditHold.objects.create(
            bid=bid,
            wallet=bidder_wallet,
            amount_credits=amount_credits,
            status=FounderCreditHold.STATUS_HELD,
        )
        _release_outbid_founder_bids(
            listing=locked_listing,
            winning_bid=bid,
        )
        return {
            "bid": bid,
            "hold": hold,
            "additional_credits_held": amount_credits,
            }

    hold = (
        FounderCreditHold.objects
        .select_for_update()
        .get(
            bid=existing_bid,
            status=FounderCreditHold.STATUS_HELD,
        )
    )

    if amount_credits <= existing_bid.amount_credits:
        raise ValidationError(
            "Raised Founder bid must exceed the current bid amount."
        )

    additional_required = (
        amount_credits - existing_bid.amount_credits
    )

    if bidder_wallet.credits < additional_required:
        raise ValidationError(
            "Bidder does not have enough available credits "
            "to raise this bid."
        )

    bidder_wallet.credits -= additional_required
    bidder_wallet.save(
        update_fields=["credits"]
    )

    existing_bid.amount_credits = amount_credits
    existing_bid.save(
        update_fields=[
            "amount_credits",
            "updated_at",
        ]
    )

    hold.amount_credits = amount_credits
    hold.save(
        update_fields=[
            "amount_credits",
            "updated_at",
        ]
    )
    _release_outbid_founder_bids(
        listing=locked_listing,
        winning_bid=existing_bid,
    )

    return {
        "bid": existing_bid,
        "hold": hold,
        "additional_credits_held": additional_required,
    }

def _release_outbid_founder_bids(
    *,
    listing,
    winning_bid,
):
    """
    Release held credits for all lower active bids on a blind listing.
    """

    losing_bids = (
        FounderBid.objects
        .select_for_update()
        .filter(
            listing=listing,
            status=FounderBid.STATUS_ACTIVE,
        )
        .exclude(pk=winning_bid.pk)
        .filter(
            amount_credits__lt=winning_bid.amount_credits,
        )
        .order_by("pk")
    )

    for losing_bid in losing_bids:
        hold = (
            FounderCreditHold.objects
            .select_for_update()
            .get(
                bid=losing_bid,
                status=FounderCreditHold.STATUS_HELD,
            )
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

        hold.status = FounderCreditHold.STATUS_RELEASED
        hold.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        losing_bid.status = FounderBid.STATUS_OUTBID
        losing_bid.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

@transaction.atomic
def close_founder_blind_listing(
    *,
    listing,
):
    """
    Close and settle one expired blind Founder listing.

    The highest remaining fully funded active bid wins.

    Tienda:
        full winning amount -> @platform

    P2P:
        85% -> seller root
        15% -> @platform

    Winning held credits are consumed, not debited again.
    Title + settlement + listing + bid/hold state + ledger are atomic.
    """

    locked_listing = (
        FounderListing.objects
        .select_for_update()
        .get(pk=listing.pk)
    )

    if locked_listing.status != FounderListing.STATUS_ACTIVE:
        raise ValidationError(
            "Founder blind listing is no longer active."
        )

    if locked_listing.sale_type != FounderListing.SALE_BLIND:
        raise ValidationError(
            "Only blind Founder listings use the blind close path."
        )

    if locked_listing.ends_at is None:
        raise ValidationError(
            "Founder blind listing has no closing time."
        )

    if locked_listing.ends_at > timezone.now():
        raise ValidationError(
            "Founder blind listing has not ended yet."
        )

    locked_asset = (
        FounderAccount.objects
        .select_for_update()
        .get(pk=locked_listing.founder_account_id)
    )

    if locked_asset.status != FounderAccount.STATUS_LISTED:
        raise ValidationError(
            "Founder property is not currently listed."
        )

    if locked_asset.owner_root_id != locked_listing.seller_root_id:
        raise ValidationError(
            "Founder listing seller no longer owns the property."
        )

    winning_bid = (
        FounderBid.objects
        .select_for_update()
        .filter(
            listing=locked_listing,
            status=FounderBid.STATUS_ACTIVE,
        )
        .order_by(
            "-amount_credits",
            "created_at",
            "pk",
        )
        .first()
    )

    if winning_bid is None:
        locked_listing.status = FounderListing.STATUS_EXPIRED
        locked_listing.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        locked_asset.status = FounderAccount.STATUS_OWNED
        locked_asset.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return {
            "sold": False,
            "listing": locked_listing,
            "founder_account": locked_asset,
        }

    winning_hold = (
        FounderCreditHold.objects
        .select_for_update()
        .get(
            bid=winning_bid,
            status=FounderCreditHold.STATUS_HELD,
        )
    )

    if winning_hold.amount_credits != winning_bid.amount_credits:
        raise ValidationError(
            "Winning Founder bid and credit hold do not match."
        )

    sale_price_credits = int(
        winning_bid.amount_credits
    )

    if sale_price_credits < FOUNDER_MIN_TRANSFER_CREDITS:
        raise ValidationError(
            "Winning Founder bid is below the transaction floor."
        )

    buyer_root = get_authoritative_root(
        winning_bid.bidder_root
    )

    seller_root = get_authoritative_root(
        locked_listing.seller_root
    )

    if buyer_root.pk == seller_root.pk:
        raise ValidationError(
            "Founder buyer and seller resolve to the same root."
        )

    system_wallet = get_system_wallet()
    platform_user = system_wallet.user

    if locked_listing.listing_source == FounderListing.SOURCE_TIENDA:
        if seller_root.pk != platform_user.pk:
            raise ValidationError(
                "Tienda Founder listing is not owned by FANZ Treasury."
            )

        platform_fee = 0
        seller_proceeds = sale_price_credits

    elif locked_listing.listing_source == FounderListing.SOURCE_P2P:
        if seller_root.pk == platform_user.pk:
            raise ValidationError(
                "Treasury inventory cannot settle through the P2P path."
            )

        platform_fee = int(
            Decimal(sale_price_credits)
            * FOUNDER_PLATFORM_FEE_RATE
        )

        seller_proceeds = (
            sale_price_credits - platform_fee
        )

    else:
        raise ValidationError(
            "Unsupported Founder listing source."
        )

    wallet_ids = {
        winning_hold.wallet_id,
        system_wallet.pk,
    }

    seller_wallet_id = None

    if locked_listing.listing_source == FounderListing.SOURCE_P2P:
        seller_wallet_id = (
            BidWallet.objects
            .get(user=seller_root)
            .pk
        )
        wallet_ids.add(seller_wallet_id)

    locked_wallets = {
        wallet.pk: wallet
        for wallet in (
            BidWallet.objects
            .select_for_update()
            .filter(pk__in=sorted(wallet_ids))
            .order_by("pk")
        )
    }

    winner_wallet = locked_wallets[
        winning_hold.wallet_id
    ]

    platform_wallet = locked_wallets[
        system_wallet.pk
    ]

    wallet_transaction_ids = []

    if locked_listing.listing_source == FounderListing.SOURCE_TIENDA:
        platform_wallet.credits += sale_price_credits
        platform_wallet.save(
            update_fields=["credits"]
        )

        sale_tx = WalletTransaction.objects.create(
            sender=winner_wallet,
            receiver=platform_wallet,
            amount=sale_price_credits,
            transaction_type="purchase",
            reference=(
                f"Founder blind Tienda sale "
                f"@{locked_asset.handle}: "
                f"price={sale_price_credits}"
            ),
        )

        wallet_transaction_ids.append(
            sale_tx.pk
        )

        transfer_type = (
            FounderOwnershipLedger
            .TRANSFER_TREASURY_RELEASE
        )

    else:
        seller_wallet = locked_wallets[
            seller_wallet_id
        ]

        seller_wallet.credits += seller_proceeds
        platform_wallet.credits += platform_fee

        seller_wallet.save(
            update_fields=["credits"]
        )

        platform_wallet.save(
            update_fields=["credits"]
        )

        seller_tx = WalletTransaction.objects.create(
            sender=winner_wallet,
            receiver=seller_wallet,
            amount=seller_proceeds,
            transaction_type="transfer",
            reference=(
                f"Founder blind sale @{locked_asset.handle}: "
                f"gross={sale_price_credits}; "
                f"seller={seller_proceeds}"
            ),
        )

        fee_tx = WalletTransaction.objects.create(
            sender=winner_wallet,
            receiver=platform_wallet,
            amount=platform_fee,
            transaction_type="transfer",
            reference=(
                f"Founder blind platform fee "
                f"@{locked_asset.handle}: "
                f"gross={sale_price_credits}; "
                f"fee={platform_fee}"
            ),
        )

        wallet_transaction_ids.extend([
            seller_tx.pk,
            fee_tx.pk,
        ])

        transfer_type = (
            FounderOwnershipLedger
            .TRANSFER_P2P_BLIND
        )

    winning_hold.status = FounderCreditHold.STATUS_CONSUMED
    winning_hold.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    winning_bid.status = FounderBid.STATUS_WON
    winning_bid.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    locked_asset.owner_root = buyer_root
    locked_asset.status = FounderAccount.STATUS_OWNED
    locked_asset.save(
        update_fields=[
            "owner_root",
            "status",
            "updated_at",
        ]
    )

    locked_listing.status = FounderListing.STATUS_SOLD
    locked_listing.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    ledger_record = append_founder_ownership_ledger(
        founder_account=locked_asset,
        seller_root=seller_root,
        buyer_root=buyer_root,
        transfer_type=transfer_type,
        sale_price_credits=sale_price_credits,
        platform_fee_credits=platform_fee,
        seller_proceeds_credits=seller_proceeds,
        wallet_transaction_ids=wallet_transaction_ids,
        metadata_snapshot={
            "seller_username": seller_root.username,
            "buyer_username": buyer_root.username,
            "handle": locked_asset.handle,
            "listing_id": locked_listing.pk,
            "winning_bid_id": winning_bid.pk,
            "listing_source": locked_listing.listing_source,
            "tienda_lane": locked_listing.tienda_lane,
        },
    )

    return {
        "sold": True,
        "listing": locked_listing,
        "founder_account": locked_asset,
        "winning_bid": winning_bid,
        "winning_hold": winning_hold,
        "seller_root": seller_root,
        "buyer_root": buyer_root,
        "sale_price_credits": sale_price_credits,
        "platform_fee_credits": platform_fee,
        "seller_proceeds_credits": seller_proceeds,
        "ledger_record": ledger_record,
    }

def normalize_owner_root(user):
    """
    Return the authoritative beneficial root for a user.
    """
    return get_authoritative_root(user)


def assign_founder_owner(*, founder_account, owner):
    """
    Assign a Founder property to the owner's authoritative root.

    The stored owner_root is always the top-most root, never a child.
    """
    if founder_account.pk is None:
        raise ValidationError(
            "Founder property must be saved before ownership is assigned."
        )

    if owner.pk is None:
        raise ValidationError(
            "Owner account must be saved."
        )

    root = get_authoritative_root(owner)

    founder_account.owner_root = root

    if founder_account.current_account is None:
        founder_account.status = FounderAccount.STATUS_OWNED

    founder_account.save(
        update_fields=[
            "owner_root",
            "status",
            "updated_at",
        ]
    )

    return root

@transaction.atomic
def create_founder_listing(
    *,
    founder_account,
    seller,
    sale_type,
    fixed_price_credits=None,
    minimum_bid_credits=None,
    ends_at=None,
):
    """
    Create one active secondary-market Founder listing.

    Only the current authoritative owner/root may list the property.
    """

    locked_asset = (
        FounderAccount.objects
        .select_for_update()
        .get(pk=founder_account.pk)
    )

    seller_root = get_authoritative_root(seller)

    if locked_asset.owner_root_id is None:
        raise ValidationError(
            "Unowned Founder property cannot be listed "
            "on the P2P marketplace."
        )

    if locked_asset.owner_root_id != seller_root.pk:
        raise ValidationError(
            "Only the authoritative Founder owner may list this property."
        )

    if locked_asset.status not in {
        FounderAccount.STATUS_OWNED,
        FounderAccount.STATUS_LISTED,
    }:
        raise ValidationError(
            "Founder property is not eligible for a P2P listing."
        )

    if FounderListing.objects.filter(
        founder_account=locked_asset,
        status=FounderListing.STATUS_ACTIVE,
    ).exists():
        raise ValidationError(
            "Founder property already has an active listing."
        )

    if sale_type == FounderListing.SALE_FIXED:
        if fixed_price_credits is None:
            raise ValidationError(
                "Fixed-price listings require a sale price."
            )

        fixed_price_credits = int(fixed_price_credits)

        if fixed_price_credits < FOUNDER_MIN_TRANSFER_CREDITS:
            raise ValidationError(
                "Fixed-price Founder listings require at least 200 credits."
            )

        if minimum_bid_credits is not None or ends_at is not None:
            raise ValidationError(
                "Fixed-price listings cannot contain blind-sale terms."
            )

    elif sale_type == FounderListing.SALE_BLIND:
        if minimum_bid_credits is None:
            raise ValidationError(
                "Blind Founder sales require a minimum bid."
            )

        minimum_bid_credits = int(minimum_bid_credits)

        if minimum_bid_credits < FOUNDER_MIN_TRANSFER_CREDITS:
            raise ValidationError(
                "Blind Founder sales require a minimum bid "
                "of at least 200 credits."
            )

        if fixed_price_credits is not None:
            raise ValidationError(
                "Blind Founder sales cannot contain a fixed price."
            )

        if ends_at is None or ends_at <= timezone.now():
            raise ValidationError(
                "Blind Founder sales require a future closing time."
            )

    else:
        raise ValidationError(
            "Unsupported Founder listing type."
        )

    listing = FounderListing.objects.create(
        founder_account=locked_asset,
        seller_root=seller_root,
        sale_type=sale_type,
        fixed_price_credits=fixed_price_credits,
        minimum_bid_credits=minimum_bid_credits,
        ends_at=ends_at,
        status=FounderListing.STATUS_ACTIVE,
    )

    locked_asset.status = FounderAccount.STATUS_LISTED
    locked_asset.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return listing

def same_authoritative_root(user_a, user_b):
    return (
        get_authoritative_root(user_a).pk
        == get_authoritative_root(user_b).pk
    )


def is_external_root_change(*, current_owner, proposed_owner):
    """
    True only when beneficial ownership moves between
    different authoritative roots.
    """
    return not same_authoritative_root(
        current_owner,
        proposed_owner,
    )

def get_direct_controller(user):
    edge = (
        AccountControl.objects
        .select_related("controller_account")
        .filter(controlled_account=user)
        .first()
    )

    if edge is None:
        return None

    return edge.controller_account


def get_authoritative_root(user):
    """
    Resolve the top-most controller for an account.

    Raises ValidationError if corrupted historical data contains a cycle.
    """
    current = user
    visited_ids = set()

    while True:
        if current.id in visited_ids:
            raise ValidationError(
                "Account control cycle detected."
            )

        visited_ids.add(current.id)

        controller = get_direct_controller(current)

        if controller is None:
            return current

        current = controller


def would_create_control_cycle(controller, controlled):
    """
    Return True if assigning controller -> controlled would create a cycle.
    """
    if controller.pk == controlled.pk:
        return True

    current = controller
    visited_ids = set()

    while current is not None:
        if current.pk == controlled.pk:
            return True

        if current.pk in visited_ids:
            raise ValidationError(
                "Existing account control cycle detected."
            )

        visited_ids.add(current.pk)
        current = get_direct_controller(current)

    return False


@transaction.atomic
def assign_account_control(*, controller, controlled):
    """
    Create or replace the direct controller of one account.

    Enforces:
    - no self-control
    - no cycles
    - one direct controller per controlled account
    """
    if controller.pk is None or controlled.pk is None:
        raise ValidationError(
            "Both controller and controlled accounts must be saved."
        )

    if controller.pk == controlled.pk:
        raise ValidationError(
            "An account cannot control itself."
        )

    if would_create_control_cycle(controller, controlled):
        raise ValidationError(
            "This control assignment would create an ownership cycle."
        )

    edge, created = AccountControl.objects.update_or_create(
        controlled_account=controlled,
        defaults={
            "controller_account": controller,
        },
    )

    return edge
