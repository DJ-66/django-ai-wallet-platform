from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .validators import (
    FOUNDER_FLOOR_CREDITS,
    validate_founder_handle,
)


LIST_PRICE_FACTOR = Decimal("0.93")
MAGIC_PRICE_MINIMUM_BUDGET = 215


@dataclass(frozen=True)
class FounderCoinIdentity:
    handle: str
    display_name: str
    symbol: str
    package_name: str
    module_name: str
    coin_struct_name: str


@dataclass(frozen=True)
class FounderBudgetQuote:
    budget_credits: int
    list_price_credits: int | None
    suggest_swamp: bool


def founder_coin_identity(handle):
    """
    Return the permanent creator-coin identity attached to one
    canonical FANZ Founder handle.

    Example:
        @zoe
        -> ZoeFanz
        -> ZOEFANZ
        -> fanz_creator_zoe
        -> zoe_fanz
        -> ZOE_FANZ
    """
    handle = validate_founder_handle(handle)

    display_prefix = (
        handle[0].upper() + handle[1:]
        if handle
        else handle
    )

    return FounderCoinIdentity(
        handle=handle,
        display_name=f"{display_prefix}Fanz",
        symbol=f"{handle.upper()}FANZ",
        package_name=f"fanz_creator_{handle}",
        module_name=f"{handle}_fanz",
        coin_struct_name=f"{handle.upper()}_FANZ",
    )


def founder_budget_quote(budget_credits):
    """
    Convert the buyer's private budget into the public List Price.

    Budget >= 215:
        List Price = 93% of budget, rounded to whole credits,
        never below the Founder floor.

    Budget <= 214:
        No calculated List Price. Suggest an available 200-credit
        Tienda swamp/wasteland Founder instead.
    """
    try:
        budget = int(budget_credits)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Budget must be a whole number of credits."
        ) from exc

    if budget <= 0:
        raise ValueError(
            "Budget must be greater than zero."
        )

    if budget < MAGIC_PRICE_MINIMUM_BUDGET:
        return FounderBudgetQuote(
            budget_credits=budget,
            list_price_credits=None,
            suggest_swamp=True,
        )

    calculated = (
        Decimal(budget)
        * LIST_PRICE_FACTOR
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    list_price = max(
        int(calculated),
        FOUNDER_FLOOR_CREDITS,
    )

    return FounderBudgetQuote(
        budget_credits=budget,
        list_price_credits=list_price,
        suggest_swamp=False,
    )
