from django.db import transaction

from .founder_vending import founder_coin_identity
from .models import (
    EconomyAsset,
    FounderAccount,
)


GENESIS_SUPPLY_BASE_UNITS = 21_000_000_000_000_000
DECIMALS = 6


class FounderCoinError(RuntimeError):
    pass


@transaction.atomic
def create_founder_coin_draft(
    *,
    founder_account_id,
    recipient_address,
    issuance_source="founder_vending",
):
    recipient_address = (
        recipient_address or ""
    ).strip()

    if not recipient_address:
        raise FounderCoinError(
            "A Sui recipient address is required "
            "before creating a Founder coin draft."
        )

    founder = (
        FounderAccount.objects
        .select_for_update()
        .get(pk=founder_account_id)
    )

    if founder.status != FounderAccount.STATUS_OWNED:
        raise FounderCoinError(
            "Founder property must be owned before "
            "its matching coin can be created."
        )

    if founder.owner_root_id is None:
        raise FounderCoinError(
            "Founder property has no authoritative owner."
        )

    identity = founder_coin_identity(
        founder.handle
    )

    existing = (
        EconomyAsset.objects
        .select_for_update()
        .filter(
            founder_account=founder
        )
        .first()
    )

    if existing is not None:
        metadata = dict(
            existing.metadata or {}
        )

        existing_recipient = (
            metadata.get(
                "intended_recipient_address"
            )
            or ""
        )

        if (
            existing_recipient
            and existing_recipient
            != recipient_address
        ):
            raise FounderCoinError(
                "Founder coin already has a different "
                "intended Sui recipient address."
            )

        return existing, False

    package_name = (
        f"fanz_creator_{identity.handle}"
    )

    asset = EconomyAsset.objects.create(
        founder_account=founder,
        name=identity.display_name,
        symbol=identity.symbol,
        chain="sui",
        decimals=DECIMALS,
        genesis_supply_base_units=(
            GENESIS_SUPPLY_BASE_UNITS
        ),
        status=EconomyAsset.STATUS_DRAFT,
        metadata={
            "generated_package":
                package_name,
            "intended_recipient_address":
                recipient_address,
            "issuance_source":
                issuance_source,
            "publication_network":
                (
                    "mainnet"
                    if issuance_source
                    == "founder_ownership"
                    else "testnet"
                ),
        },
    )

    return asset, True


@transaction.atomic
def create_coin_draft_for_purchased_cart_item(
    *,
    cart_item,
):
    if not cart_item.sui_recipient_address:
        return None, False

    if cart_item.status != cart_item.STATUS_PURCHASED:
        raise FounderCoinError(
            "Founder cart item must be purchased "
            "before coin creation."
        )

    founder = (
        FounderAccount.objects
        .filter(
            handle=cart_item.wanted_handle
        )
        .first()
    )

    if founder is None:
        raise FounderCoinError(
            "Purchased Founder property does not exist."
        )

    return create_founder_coin_draft(
        founder_account_id=founder.pk,
        recipient_address=(
            cart_item.sui_recipient_address
        ),
    )
