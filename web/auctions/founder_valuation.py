from datetime import timedelta
from math import pow

from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.utils import timezone

from .models import (
    FeedPost,
    FounderListing,
    FounderOwnershipLedger,
)


# ---------------------------------------------------------
# FANZ Founder valuation policy
# ---------------------------------------------------------

FOUNDER_MINIMUM_CREDITS = 200

ACTIVE_DEVELOPMENT_MIN_DAYS = 182
ACTIVE_DEVELOPMENT_POSTS_PER_WEEK = 3

ANNUAL_ACTIVE_GROWTH_RATE = 0.40

BUYBACK_FLOOR_RATIO = 0.50


def _round_credits(value):
    return max(
        FOUNDER_MINIMUM_CREDITS,
        int(round(float(value))),
    )


def _structural_multiplier(founder_account):
    """
    Deterministic v0.1 intrinsic property multiplier.

    This intentionally measures only structural utility:
    short clean alphabetic handles receive a premium.

    Phase 12 can later add semantic/name/category scoring
    from the FANZ knowledge graph.

    Examples:
        @ai     -> strong structural value
        @tea    -> strong structural value
        @box    -> strong structural value
        @q-9_   -> floor structural value
    """

    handle = (founder_account.handle or "").strip()
    length = len(handle)

    if handle.isalpha():
        if length == 1:
            return 4.00

        if length == 2:
            return 3.00

        if length == 3:
            return 2.00

        if length == 4:
            return 1.50

    if handle.isalnum():
        if length <= 2:
            return 2.00

        if length == 3:
            return 1.50

        return 1.25

    return 1.00


def _growth_multiplier(years):
    """
    40% annual compounded Active Development growth.
    """

    years = max(
        0.0,
        float(years),
    )

    return pow(
        1.0 + ANNUAL_ACTIVE_GROWTH_RATE,
        years,
    )


def _get_latest_transfer(founder_account):
    return (
        FounderOwnershipLedger.objects
        .filter(
            founder_account=founder_account,
        )
        .select_related(
            "seller_root",
            "buyer_root",
        )
        .order_by("-sequence")
        .first()
    )


def _get_last_market_sale(founder_account):
    return (
        FounderOwnershipLedger.objects
        .filter(
            founder_account=founder_account,
            transfer_type__in=[
                FounderOwnershipLedger.TRANSFER_P2P_FIXED,
                FounderOwnershipLedger.TRANSFER_P2P_BLIND,
                FounderOwnershipLedger.TRANSFER_MINIMUM_CONVEYANCE,
            ],
        )
        .order_by("-sequence")
        .first()
    )


def _get_active_listing(founder_account):
    return (
        FounderListing.objects
        .filter(
            founder_account=founder_account,
            status=FounderListing.STATUS_ACTIVE,
        )
        .first()
    )


def _development_stats(
    founder_account,
    *,
    as_of,
    acquired_at,
):
    """
    Development v0.1.

    The operating account is the Founder current_account when
    available. Otherwise owner_root is used.

    This uses public posting history only.

    Likes, tips, fans, unlocks, donations, hashtag relevance,
    etc. will become additional Phase 12 development signals.
    """

    operator = (
        founder_account.current_account
        or founder_account.owner_root
    )

    if operator is None:
        return {
            "operator": None,
            "ownership_days": 0,
            "ownership_weeks": 0.0,
            "public_posts": 0,
            "posts_per_week": 0.0,
            "qualifying_weeks": 0,
            "active_development": False,
        }

    ownership_days = max(
        0,
        (as_of - acquired_at).days,
    )

    ownership_weeks = max(
        ownership_days / 7.0,
        1.0,
    )

    posts = (
        FeedPost.objects
        .filter(
            user=operator,
            is_public=True,
            created_at__gte=acquired_at,
            created_at__lte=as_of,
        )
    )

    public_posts = posts.count()

    posts_per_week = (
        public_posts
        / ownership_weeks
    )

    weekly_rows = (
        posts
        .annotate(
            week=TruncWeek("created_at"),
        )
        .values("week")
        .annotate(
            post_count=Count("id"),
        )
        .order_by()
    )

    qualifying_weeks = sum(
        1
        for row in weekly_rows
        if row["post_count"] >= ACTIVE_DEVELOPMENT_POSTS_PER_WEEK
    )

    age_qualified = (
        ownership_days
        >= ACTIVE_DEVELOPMENT_MIN_DAYS
    )

    posting_qualified = (
        posts_per_week
        >= ACTIVE_DEVELOPMENT_POSTS_PER_WEEK
    )

    active_development = (
        age_qualified
        and posting_qualified
    )

    return {
        "operator": operator,
        "ownership_days": ownership_days,
        "ownership_weeks": round(
            ownership_weeks,
            2,
        ),
        "public_posts": public_posts,
        "posts_per_week": round(
            posts_per_week,
            2,
        ),
        "qualifying_weeks": qualifying_weeks,
        "active_development": active_development,
    }


def get_founder_valuation(
    founder_account,
    *,
    as_of=None,
):
    """
    Deterministic FANZ Founder valuation v0.1.

    FANZ estimates.
    Owners price.
    Buyers decide.

    Only the CURRENT qualified buyback floor is actionable.
    Future floors are projections assuming continued
    Active Development.
    """

    as_of = as_of or timezone.now()

    latest_transfer = _get_latest_transfer(
        founder_account
    )

    active_listing = _get_active_listing(
        founder_account
    )

    last_market_sale = _get_last_market_sale(
        founder_account
    )

    if latest_transfer:
        acquisition_price = int(
            latest_transfer.sale_price_credits
        )

        acquired_at = latest_transfer.created_at

    else:
        acquisition_price = max(
            int(
                founder_account.floor_price_credits
                or FOUNDER_MINIMUM_CREDITS
            ),
            FOUNDER_MINIMUM_CREDITS,
        )

        acquired_at = founder_account.created_at

    development = _development_stats(
        founder_account,
        as_of=as_of,
        acquired_at=acquired_at,
    )

    structural_multiplier = (
        _structural_multiplier(
            founder_account
        )
    )

    ownership_years = max(
        development["ownership_days"] / 365.25,
        0.0,
    )

    # -----------------------------------------------------
    # Current estimated value
    # -----------------------------------------------------

    base_value = max(
        acquisition_price,
        FOUNDER_MINIMUM_CREDITS,
    )

    intrinsic_value = (
        base_value
        * structural_multiplier
    )

    if development["active_development"]:
        current_growth = _growth_multiplier(
            ownership_years
        )
    else:
        current_growth = 1.0

    current_estimate = _round_credits(
        intrinsic_value
        * current_growth
    )

    # -----------------------------------------------------
    # Forward estimates
    #
    # These assume continued Active Development.
    # -----------------------------------------------------

    estimate_2y = _round_credits(
        current_estimate
        * _growth_multiplier(2)
    )

    estimate_5y = _round_credits(
        current_estimate
        * _growth_multiplier(5)
    )

    estimate_10y = _round_credits(
        current_estimate
        * _growth_multiplier(10)
    )

    # -----------------------------------------------------
    # FANZ liquidity / pawn-shop floor
    # -----------------------------------------------------

    current_floor = _round_credits(
        current_estimate
        * BUYBACK_FLOOR_RATIO
    )

    floor_2y = _round_credits(
        estimate_2y
        * BUYBACK_FLOOR_RATIO
    )

    floor_5y = _round_credits(
        estimate_5y
        * BUYBACK_FLOOR_RATIO
    )

    floor_10y = _round_credits(
        estimate_10y
        * BUYBACK_FLOOR_RATIO
    )

    # -----------------------------------------------------
    # Open-market evidence
    # -----------------------------------------------------

    asking_price = None
    minimum_offer = None
    listing_type = None

    if active_listing:
        listing_type = active_listing.sale_type

        if (
            active_listing.sale_type
            == FounderListing.SALE_FIXED
        ):
            asking_price = (
                active_listing.fixed_price_credits
            )

        elif (
            active_listing.sale_type
            == FounderListing.SALE_BLIND
        ):
            minimum_offer = (
                active_listing.minimum_bid_credits
            )

    eligible_at = (
        acquired_at
        + timedelta(
            days=ACTIVE_DEVELOPMENT_MIN_DAYS
        )
    )

    return {
        "founder_account": founder_account,

        "basis": {
            "acquisition_price_credits": acquisition_price,
            "acquired_at": acquired_at,
            "structural_multiplier": structural_multiplier,
        },

        "estimated_value": {
            "current": current_estimate,
            "year_2": estimate_2y,
            "year_5": estimate_5y,
            "year_10": estimate_10y,
        },

        "buyback_floor": {
            "ratio": BUYBACK_FLOOR_RATIO,
            "qualified_now": development[
                "active_development"
            ],
            "eligible_at": eligible_at,
            "current": current_floor,
            "year_2": floor_2y,
            "year_5": floor_5y,
            "year_10": floor_10y,
        },

        "development": development,

        "market": {
            "active_listing": active_listing,
            "listing_type": listing_type,
            "asking_price_credits": asking_price,
            "minimum_offer_credits": minimum_offer,

            # Do NOT expose active blind high-bid amounts.
            "last_market_sale_credits": (
                int(
                    last_market_sale.sale_price_credits
                )
                if last_market_sale
                else None
            ),
        },

        "provenance": {
            "latest_transfer": latest_transfer,
            "ledger_sequence": (
                latest_transfer.sequence
                if latest_transfer
                else None
            ),
            "record_hash": (
                latest_transfer.record_hash
                if latest_transfer
                else ""
            ),
        },
    }
