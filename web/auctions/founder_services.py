from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .founder_ledger import append_founder_ownership_ledger
from .models import (
    AccountControl,
    BidWallet,
    FounderAccount,
    FounderOwnershipLedger,
    WalletTransaction,
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
