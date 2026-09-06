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

    asset = (
        EconomyAsset.objects
        .select_for_update()
        .select_related("founder_account")
        .get(pk=asset_id)
    )

    founder = asset.founder_account

    if founder.owner_root_id != user.pk:
        raise CoinRebrandPaymentError(
            "You do not currently own this Founder property."
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
            ""
        )
    ).strip()

    if (
        not expected_publication_key
        or expected_publication_key
        != str(publication_key).strip()
    ):
        raise CoinRebrandPaymentError(
            "Founder coin publication does not match."
        )

    normalized_icon_url = str(
        icon_url or ""
    ).strip()

    if not normalized_icon_url:
        raise CoinRebrandPaymentError(
            "Coin image URL is required."
        )

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
