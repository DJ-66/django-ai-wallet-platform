from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    BidWallet,
    EconomyAsset,
    PaymentIntent,
    WalletTransaction,
)
from .utils import get_system_wallet


REBRAND_CREDITS = 100
REBRAND_USD = Decimal("5.00")
SERVICE_KEY = "founder_coin_rebrand"


class CoinRebrandPaymentError(Exception):
    pass


def validate_coin_rebrand_request(
    *,
    user,
    asset_id,
    publication_key,
    icon_url,
    lock_asset=False,
):
    """
    Validate and normalize one exact Coin Rebrand
    request without charging any payment rail.

    Returns:
        (asset, publication_key, icon_url)
    """
    queryset = (
        EconomyAsset.objects
        .select_related("founder_account")
    )

    if lock_asset:
        queryset = queryset.select_for_update()

    asset = queryset.get(pk=asset_id)

    founder = asset.founder_account

    if founder.owner_root_id != user.pk:
        raise CoinRebrandPaymentError(
            "You do not currently own this "
            "Founder property."
        )

    if asset.status != EconomyAsset.STATUS_ACTIVE:
        raise CoinRebrandPaymentError(
            "Founder coin is not active."
        )

    if asset.chain != "sui":
        raise CoinRebrandPaymentError(
            "Founder coin is not a Sui asset."
        )

    expected_publication_key = str(
        (asset.metadata or {}).get(
            "publication_key",
            "",
        )
    ).strip()

    if (
        not expected_publication_key
        or expected_publication_key
        != str(publication_key).strip()
    ):
        raise CoinRebrandPaymentError(
            "Founder coin publication "
            "does not match."
        )

    normalized_icon_url = str(
        icon_url or ""
    ).strip()

    if not normalized_icon_url:
        raise CoinRebrandPaymentError(
            "Coin image URL is required."
        )

    return (
        asset,
        expected_publication_key,
        normalized_icon_url,
    )


def bind_paid_coin_rebrand_entitlement(
    *,
    payment_intent,
):
    """
    Bind one already-paid PaymentIntent to an exact
    Coin Rebrand entitlement.

    This does not charge any payment rail and does not
    execute the Sui rebrand transaction.
    """
    if not isinstance(
        payment_intent,
        PaymentIntent,
    ):
        raise TypeError(
            "payment_intent must be a PaymentIntent"
        )

    if payment_intent.user_id is None:
        raise CoinRebrandPaymentError(
            "Coin Rebrand payment has no user."
        )

    metadata = dict(
        payment_intent.metadata or {}
    )

    try:
        asset_id = int(
            metadata["asset_id"]
        )
        publication_key = str(
            metadata["publication_key"]
        ).strip()
        icon_url = str(
            metadata["icon_url"]
        ).strip()
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise CoinRebrandPaymentError(
            "Coin Rebrand payment has invalid metadata."
        ) from exc

    (
        asset,
        expected_publication_key,
        normalized_icon_url,
    ) = validate_coin_rebrand_request(
        user=payment_intent.user,
        asset_id=asset_id,
        publication_key=publication_key,
        icon_url=icon_url,
        lock_asset=False,
    )

    metadata.update({
        "service": SERVICE_KEY,
        "asset_id": asset.pk,
        "publication_key":
            expected_publication_key,
        "icon_url":
            normalized_icon_url,
        "owner_root_id":
            payment_intent.user_id,
    })

    payment_intent.metadata = metadata
    payment_intent.save(
        update_fields=[
            "metadata",
            "updated_at",
        ]
    )

    return payment_intent


def prepare_coin_rebrand_transaction(
    *,
    publication_key,
    icon_url,
    expected_image_action,
):
    """
    Prepare the owner-signed Sui Coin Image transaction.

    Payment/entitlement must already have been handled by
    the caller when expected_image_action == "rebrand".

    This function does not charge any payment rail.
    """
    from .sui_adapter import (
        SuiAdapterError,
        prepare_creator_coin_image_rebrand,
    )

    response = prepare_creator_coin_image_rebrand(
        publication_key,
        icon_url=icon_url,
    )

    prepared = response.get("prepared")

    if not isinstance(prepared, dict):
        raise SuiAdapterError(
            "Sui service returned no prepared "
            "Coin Image transaction."
        )

    prepared_action = str(
        prepared.get(
            "image_action",
            "",
        )
    ).strip().lower()

    if prepared_action != expected_image_action:
        raise SuiAdapterError(
            "Coin Image state changed while "
            "preparing the transaction. "
            "Please try again."
        )

    return prepared


def get_paid_coin_rebrand_entitlement(
    *,
    user,
    payment_intent_id,
):
    """
    Return and revalidate one fulfilled external
    Coin Rebrand entitlement owned by this user.
    """
    try:
        intent = (
            PaymentIntent.objects
            .select_related(
                "vending_product",
                "user",
            )
            .get(
                pk=payment_intent_id,
                user=user,
                purpose="platform_service",
                status="fulfilled",
                vending_product__product_key=(
                    "founder-coin-rebrand"
                ),
                vending_product__fulfillment_type=(
                    "coin_rebrand"
                ),
                metadata__service=SERVICE_KEY,
                metadata__owner_root_id=user.pk,
            )
        )
    except PaymentIntent.DoesNotExist as exc:
        raise CoinRebrandPaymentError(
            "Paid Coin Rebrand entitlement "
            "was not found."
        ) from exc

    metadata = intent.metadata or {}

    try:
        asset_id = int(
            metadata["asset_id"]
        )
        publication_key = str(
            metadata["publication_key"]
        ).strip()
        icon_url = str(
            metadata["icon_url"]
        ).strip()
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise CoinRebrandPaymentError(
            "Paid Coin Rebrand entitlement "
            "has invalid metadata."
        ) from exc

    (
        asset,
        publication_key,
        icon_url,
    ) = validate_coin_rebrand_request(
        user=user,
        asset_id=asset_id,
        publication_key=publication_key,
        icon_url=icon_url,
        lock_asset=False,
    )

    return (
        intent,
        asset,
        publication_key,
        icon_url,
    )


def create_coin_rebrand_vending_checkout(
    *,
    user,
    asset_id,
    publication_key,
    icon_url,
    payment_method,
):
    """
    Create and prepare one externally paid Coin Rebrand
    checkout using the reusable FANZ vending chassis.

    Supported here:
        BTC
        DOGE
        SUI

    FANZ Credits remain a FANZ-only synchronous path.
    """
    from .models import VendingProduct
    from .vending_services import (
        VendingProductError,
        create_vending_payment_intent,
        prepare_vending_checkout,
    )

    (
        asset,
        expected_publication_key,
        normalized_icon_url,
    ) = validate_coin_rebrand_request(
        user=user,
        asset_id=asset_id,
        publication_key=publication_key,
        icon_url=icon_url,
        lock_asset=False,
    )

    product = VendingProduct.objects.get(
        product_key="founder-coin-rebrand",
        fulfillment_type="coin_rebrand",
        is_active=True,
    )

    try:
        intent = create_vending_payment_intent(
            product=product,
            buyer=user,
            payment_method=payment_method,
            purpose="platform_service",
            metadata={
                "service": SERVICE_KEY,
                "asset_id": asset.pk,
                "publication_key":
                    expected_publication_key,
                "icon_url":
                    normalized_icon_url,
                "owner_root_id": user.pk,
                "storefront": "founder_bakery",
            },
        )

        intent = prepare_vending_checkout(
            payment_intent=intent
        )

    except VendingProductError as exc:
        raise CoinRebrandPaymentError(
            str(exc)
        ) from exc

    return intent


@transaction.atomic
def purchase_coin_rebrand_with_credits(
    *,
    user,
    asset_id,
    publication_key,
    icon_url,
):
    """
    Create or reuse one exact paid FANZ Bakery entitlement.

    The entitlement is bound to:
      - owner
      - asset
      - publication
      - exact icon URL

    Repeated calls for the same exact request are idempotent.
    """

    (
        asset,
        expected_publication_key,
        normalized_icon_url,
    ) = validate_coin_rebrand_request(
        user=user,
        asset_id=asset_id,
        publication_key=publication_key,
        icon_url=icon_url,
        lock_asset=True,
    )

    founder = asset.founder_account

    #
    # Exact-entitlement idempotency.
    #
    existing = (
        PaymentIntent.objects
        .filter(
            user=user,
            purpose="platform_service",
            settlement_source=(
                PaymentIntent.SETTLEMENT_INTERNAL
            ),
            amount=REBRAND_USD,
            currency="USD",
            status="fulfilled",
            metadata__service=SERVICE_KEY,
            metadata__asset_id=asset.pk,
            metadata__publication_key=(
                expected_publication_key
            ),
            metadata__icon_url=normalized_icon_url,
            metadata__owner_root_id=user.pk,
        )
        .order_by("-id")
        .first()
    )

    if existing is not None:
        return existing, False

    system_wallet = get_system_wallet()

    wallet_ids = sorted({
        system_wallet.pk,
        BidWallet.objects.get(user=user).pk,
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

    buyer_wallet = next(
        (
            wallet
            for wallet in locked_wallets.values()
            if wallet.user_id == user.pk
        ),
        None,
    )

    platform_wallet = locked_wallets.get(
        system_wallet.pk
    )

    if buyer_wallet is None:
        raise CoinRebrandPaymentError(
            "Buyer wallet could not be locked."
        )

    if platform_wallet is None:
        raise CoinRebrandPaymentError(
            "FANZ platform wallet could not be locked."
        )

    if buyer_wallet.pk == platform_wallet.pk:
        raise CoinRebrandPaymentError(
            "Platform wallet cannot purchase a Bakery rebrand."
        )

    if buyer_wallet.credits < REBRAND_CREDITS:
        raise CoinRebrandPaymentError(
            "Insufficient FANZ Credits. "
            "Coin rebrand costs 100 credits ($5.00)."
        )

    buyer_wallet.credits -= REBRAND_CREDITS
    platform_wallet.credits += REBRAND_CREDITS

    buyer_wallet.save(
        update_fields=["credits"]
    )
    platform_wallet.save(
        update_fields=["credits"]
    )

    wallet_tx = WalletTransaction.objects.create(
        sender=buyer_wallet,
        receiver=platform_wallet,
        amount=REBRAND_CREDITS,
        transaction_type="purchase",
        reference=(
            "FANZ Bakery coin rebrand: "
            f"@{founder.handle}; "
            f"asset={asset.pk}; "
            f"publication={expected_publication_key}; "
            f"icon={normalized_icon_url}"
        ),
    )

    now = timezone.now()

    intent = PaymentIntent.objects.create(
        user=user,
        purpose="platform_service",
        status="fulfilled",
        amount=REBRAND_USD,
        currency="USD",
        settlement_source=(
            PaymentIntent.SETTLEMENT_INTERNAL
        ),
        settlement_reference=(
            f"wallet-transaction:{wallet_tx.pk}"
        ),
        metadata={
            "service": SERVICE_KEY,
            "asset_id": asset.pk,
            "publication_key":
                expected_publication_key,
            "icon_url":
                normalized_icon_url,
            "owner_root_id":
                user.pk,
            "wallet_transaction_id":
                wallet_tx.pk,
            "payment_method":
                "credits",
            "credits_charged":
                REBRAND_CREDITS,
        },
        paid_at=now,
        fulfilled_at=now,
    )

    return intent, True
