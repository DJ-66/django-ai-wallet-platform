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

# A Founder property reaches basic FANZ liquidity eligibility
# after approximately six months of ownership. Active Development
# is NOT required for capital-basis protection.
FOUNDER_LIQUIDITY_MIN_DAYS = 182

ACTIVE_DEVELOPMENT_MIN_DAYS = 182
ACTIVE_DEVELOPMENT_POSTS_PER_WEEK = 3

# Active Development is an earned accelerator layered on top
# of passive Founder scarcity/platform appreciation.
ANNUAL_ACTIVE_GROWTH_RATE = 0.40

BUYBACK_FLOOR_RATIO = 0.50

# Passive Founder-property appreciation targets.
#
# These represent scarcity/platform valuation targets, not
# guaranteed market-sale prices.
PASSIVE_VALUE_TARGETS = {
    0: 1.00,
    2: 2.00,
    5: 6.00,
    10: 15.00,
}

def _round_credits(
    value,
    *,
    minimum=FOUNDER_MINIMUM_CREDITS,
):
    rounded = int(round(float(value)))

    if minimum is None:
        return max(0, rounded)

    return max(
        int(minimum),
        rounded,
    )

def _structural_multiplier(founder_account):
    """
    Deterministic v0.2 intrinsic-property multiplier.

    Shortness and character quality provide a modest intrinsic
    premium. Semantic/category scoring will be added later from
    deterministic FANZ knowledge-graph signals.

    Scarcity/platform appreciation and Active Development are
    deliberately calculated separately.
    """
    handle = (founder_account.handle or "").strip()
    length = len(handle)

    if handle.isalpha():
        return {
            1: 1.50,
            2: 1.40,
            3: 1.30,
            4: 1.20,
        }.get(length, 1.00)

    if handle.isalnum():
        return {
            1: 1.40,
            2: 1.30,
            3: 1.20,
            4: 1.10,
        }.get(length, 1.00)

    # Wasteland / mixed-character properties retain their basis
    # but receive no automatic structural premium in v0.2.
    return 1.00

def _passive_value_multiplier(years):
    """
    Passive Founder scarcity/platform appreciation v0.2.

    Target curve:
        acquisition -> 1x
        year 2      -> 2x
        year 5      -> 6x
        year 10     -> 15x

    Values between milestones are linearly interpolated.
    Beyond year 10, v0.2 holds the 15x target rather than
    inventing an indefinite appreciation curve.
    """
    years = max(0.0, float(years))

    milestones = sorted(PASSIVE_VALUE_TARGETS.items())

    if years <= milestones[0][0]:
        return milestones[0][1]

    for index in range(1, len(milestones)):
        previous_year, previous_value = milestones[index - 1]
        next_year, next_value = milestones[index]

        if years <= next_year:
            span = next_year - previous_year
            progress = (years - previous_year) / span

            return previous_value + (
                (next_value - previous_value)
                * progress
            )

    return milestones[-1][1]


def _growth_multiplier(years):
    """
    Earned Active Development accelerator:
    40% annual compounded.

    This is separate from passive Founder scarcity/platform
    appreciation.
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
    Deterministic FANZ Founder valuation v0.2.

    FANZ estimates.
    Owners price.
    Buyers decide.

    Founder property receives passive scarcity/platform
    appreciation independent of owner activity.

    Active Development is an earned accelerator.

    After the minimum holding period, actionable FANZ
    liquidity is the greater of recognized capital basis
    or the conservative buyback ratio.

    Presentation/localization belongs outside this engine.
    """

    as_of = as_of or timezone.now()

    latest_transfer = _get_latest_transfer(
        founder_account
    )

    active_listing = _get_active_listing(
        founder_account
    )
    # -----------------------------------------------------
    # Trusted FANZ primary-market evidence
    #
    # A current fixed-price Founder Tienda listing is a
    # FANZ Treasury valuation signal.
    #
    # P2P asking prices and blind minimums are NOT valuation
    # evidence and must never raise the FANZ estimate.
    # -----------------------------------------------------

    treasury_offering_value = None

    if (
        active_listing
        and active_listing.listing_source
        == FounderListing.SOURCE_TIENDA
        and active_listing.sale_type
        == FounderListing.SALE_FIXED
        and active_listing.fixed_price_credits
    ):
        treasury_offering_value = int(
            active_listing.fixed_price_credits
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
    # Founder valuation v0.2
    #
    # Layer 1: capital basis
    # Layer 2: intrinsic property characteristics
    # Layer 3: passive scarcity/platform appreciation
    # Layer 4: earned Active Development
    # -----------------------------------------------------

    capital_basis = max(
        acquisition_price,
        FOUNDER_MINIMUM_CREDITS,
    )

    intrinsic_value = _round_credits(
        capital_basis
        * structural_multiplier
    )

    passive_multiplier = _passive_value_multiplier(
        ownership_years
    )

    passive_value = _round_credits(
        intrinsic_value
        * passive_multiplier
    )

    # -----------------------------------------------------
    # Recognized current property value
    #
    # Structural/passive valuation remains visible as the
    # deterministic model value.
    #
    # FANZ Treasury may establish a higher current primary-
    # market value through an active fixed Tienda listing.
    # -----------------------------------------------------

    recognized_current_value = passive_value

    if treasury_offering_value is not None:
        recognized_current_value = max(
            recognized_current_value,
            treasury_offering_value,
        )

    if development["active_development"]:
        development_multiplier = _growth_multiplier(
            ownership_years
        )
    else:
        development_multiplier = 1.0

    current_estimate = _round_credits(
        recognized_current_value
        * development_multiplier
    )

    development_value = max(
        0,
        current_estimate
        - recognized_current_value,
    )

    # -----------------------------------------------------
    # Conditional forward estimates
    # -----------------------------------------------------

    def projected_value(target_age_years):
        projection_age = max(
            ownership_years,
            float(target_age_years),
        )

        target_passive = _passive_value_multiplier(
            projection_age
        )

        projection_base = max(
            intrinsic_value,
            treasury_offering_value or 0,
        )

        projected = (
            projection_base
            * target_passive
        )

        if development["active_development"]:
            projected *= _growth_multiplier(
                projection_age
            )

        return _round_credits(projected)

    estimate_2y = projected_value(2)
    estimate_5y = projected_value(5)
    estimate_10y = projected_value(10)

    # -----------------------------------------------------
    # FANZ liquidity / capital protection
    # -----------------------------------------------------

    liquidity_age_qualified = (
        development["ownership_days"]
        >= FOUNDER_LIQUIDITY_MIN_DAYS
    )

    estimated_current_floor = _round_credits(
        current_estimate
        * BUYBACK_FLOOR_RATIO,
        minimum=None,
    )

    if liquidity_age_qualified:
        actionable_current = max(
            capital_basis,
            estimated_current_floor,
        )
    else:
        actionable_current = None

    floor_2y = max(
        capital_basis,
        _round_credits(
            estimate_2y * BUYBACK_FLOOR_RATIO,
            minimum=None,
        ),
    )

    floor_5y = max(
        capital_basis,
        _round_credits(
            estimate_5y * BUYBACK_FLOOR_RATIO,
            minimum=None,
        ),
    )

    floor_10y = max(
        capital_basis,
        _round_credits(
            estimate_10y * BUYBACK_FLOOR_RATIO,
            minimum=None,
        ),
    )


    # -----------------------------------------------------
    # Canonical presentation/status keys
    #
    # These are language-independent. Templates/presentation
    # layers translate them into EN / ES / PT.
    # -----------------------------------------------------

    reason_codes = []

    if structural_multiplier > 1.0:
        reason_codes.append(
            "intrinsic_structural_premium"
        )
    else:
        reason_codes.append(
            "intrinsic_standard"
        )

    reason_codes.append(
        "passive_scarcity_appreciation"
    )

    if liquidity_age_qualified:
        liquidity_status = (
            "founder_liquidity_available"
        )
    else:
        liquidity_status = (
            "founder_liquidity_pending"
        )

    if development["active_development"]:
        development_status = (
            "active_development_qualified"
        )
        reason_codes.append(
            "active_development_growth"
        )
    else:
        development_status = (
            "active_development_not_qualified"
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

    liquidity_eligible_at = (
        acquired_at
        + timedelta(
            days=FOUNDER_LIQUIDITY_MIN_DAYS
        )
    )

    development_eligible_at = (
        acquired_at
        + timedelta(
            days=ACTIVE_DEVELOPMENT_MIN_DAYS
        )
    )

    return {
        "founder_account": founder_account,

        "basis": {
            "capital_basis_credits": capital_basis,
            "acquisition_price_credits": acquisition_price,
            "acquired_at": acquired_at,
            "structural_multiplier": structural_multiplier,
            "treasury_offering_value_credits": (
                treasury_offering_value
        ),
        },

        "estimated_value": {
            "intrinsic": intrinsic_value,
            "passive": passive_value,
            "recognized_current": recognized_current_value,
            "development": development_value,
            "current": current_estimate,
            "year_2": estimate_2y,
            "year_5": estimate_5y,
            "year_10": estimate_10y,
        },

        "multipliers": {
            "structural": structural_multiplier,
            "passive_current": passive_multiplier,
            "active_development": development_multiplier,
        },

        "presentation": {
            "valuation_version": "0.2",
            "liquidity_status": liquidity_status,
            "development_status": development_status,
            "reason_codes": reason_codes,
        },

        "buyback_floor": {
            "ratio": BUYBACK_FLOOR_RATIO,

            "liquidity_qualified_now": (
                liquidity_age_qualified
            ),
            "liquidity_eligible_at": (
                liquidity_eligible_at
            ),

            "development_qualified_now": development[
                "active_development"
            ],
            "development_eligible_at": (
                development_eligible_at
            ),

            "estimated_current": (
                estimated_current_floor
            ),
            "actionable_current": (
                actionable_current
            ),

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
