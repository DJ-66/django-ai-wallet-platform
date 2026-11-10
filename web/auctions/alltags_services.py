"""Atomic billing for permanent FANZ #allTags promotions."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    AllTagsPromotion,
    BidWallet,
    FeedPost,
    WalletTransaction,
)
from .services import _get_public_discovery_eligible_posts
from .utils import get_system_wallet


class AllTagsPromotionDenied(ValidationError):
    """An expected, non-billable promotion rejection."""

    INSUFFICIENT_CREDITS = "insufficient_credits"
    DAILY_LIMIT = "daily_limit"
    INELIGIBLE_POST = "ineligible_post"

    def __init__(self, reason):
        self.reason = reason
        messages = {
            self.INSUFFICIENT_CREDITS:
                "Insufficient credits (no charge)",
            self.DAILY_LIMIT:
                "Daily limit reached (no charge)",
            self.INELIGIBLE_POST:
                "Post published normally (no charge)",
        }
        super().__init__(messages[reason])


ALLTAGS_PRICE_CREDITS = 20
ALLTAGS_COOLDOWN = timedelta(hours=24)


@transaction.atomic
def purchase_alltags_promotion(*, creator, post):
    """
    Purchase permanent universal hashtag distribution.

    Caller must ensure this transaction is part of the
    successful publication flow when publishing a new post.
    """

    User = get_user_model()

    locked_creator = (
        User.objects
        .select_for_update()
        .get(pk=creator.pk)
    )

    post = (
        FeedPost.objects
        .select_for_update()
        .get(pk=post.pk)
    )

    if post.user_id != locked_creator.pk:
        raise ValidationError(
            "Only the post creator may purchase promotion."
        )

    if not post.is_public or post.is_paid:
        raise AllTagsPromotionDenied(
            AllTagsPromotionDenied.INELIGIBLE_POST
        )

    if not (
        _get_public_discovery_eligible_posts()
        .filter(pk=post.pk)
        .exists()
    ):
        raise AllTagsPromotionDenied(
            AllTagsPromotionDenied.INELIGIBLE_POST
        )

    existing = AllTagsPromotion.objects.filter(
        post=post,
    ).first()

    if existing is not None:
        raise ValidationError(
            "This post already has an #allTags promotion."
        )

    now = timezone.now()

    recent = AllTagsPromotion.objects.filter(
        creator=locked_creator,
        created_at__gt=now - ALLTAGS_COOLDOWN,
    ).exists()

    if recent:
        raise AllTagsPromotionDenied(
            AllTagsPromotionDenied.DAILY_LIMIT
        )

    system_wallet = get_system_wallet()

    wallet_ids = sorted({
        system_wallet.pk,
        BidWallet.objects.get(user=locked_creator).pk,
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
            if wallet.user_id == locked_creator.pk
        ),
        None,
    )

    platform_wallet = locked_wallets.get(
        system_wallet.pk
    )

    if buyer_wallet is None or platform_wallet is None:
        raise ValidationError(
            "Promotion wallets could not be locked."
        )

    if buyer_wallet.pk == platform_wallet.pk:
        raise ValidationError(
            "Platform wallet cannot purchase promotion."
        )

    if buyer_wallet.credits < ALLTAGS_PRICE_CREDITS:
        raise AllTagsPromotionDenied(
            AllTagsPromotionDenied.INSUFFICIENT_CREDITS
        )

    buyer_wallet.credits -= ALLTAGS_PRICE_CREDITS
    platform_wallet.credits += ALLTAGS_PRICE_CREDITS

    buyer_wallet.save(update_fields=["credits"])
    platform_wallet.save(update_fields=["credits"])

    payment = WalletTransaction.objects.create(
        sender=buyer_wallet,
        receiver=platform_wallet,
        amount=ALLTAGS_PRICE_CREDITS,
        transaction_type="purchase",
        reference=f"alltags:post:{post.pk}",
    )

    promotion = AllTagsPromotion.objects.create(
        creator=locked_creator,
        post=post,
        wallet_transaction=payment,
        price_credits=ALLTAGS_PRICE_CREDITS,
    )

    return promotion
