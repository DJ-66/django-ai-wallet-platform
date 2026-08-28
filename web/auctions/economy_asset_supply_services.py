from django.db import transaction
from django.utils import timezone

from .models import EconomyAsset
from .sui_adapter import (
    SuiAdapterError,
    get_creator_publication_supply,
)


class EconomyAssetSupplyError(RuntimeError):
    pass


def verify_economy_asset_fixed_supply(
    asset_id,
    publication_key,
):
    asset = (
        EconomyAsset.objects
        .select_related("founder_account")
        .get(pk=asset_id)
    )

    if not asset.coin_type:
        raise EconomyAssetSupplyError(
            "EconomyAsset has no coin_type."
        )

    if not asset.genesis_tx_digest:
        raise EconomyAssetSupplyError(
            "EconomyAsset has no genesis transaction digest."
        )

    try:
        response = get_creator_publication_supply(
            publication_key
        )
    except SuiAdapterError as exc:
        raise EconomyAssetSupplyError(
            "FANZ Sui supply verification failed."
        ) from exc

    remote = response.get("supply")

    if not isinstance(remote, dict):
        raise EconomyAssetSupplyError(
            "FANZ Sui response contained no supply object."
        )

    expected = {
        "publication_key": publication_key,
        "coin_type": asset.coin_type,
        "decimals": asset.decimals,
        "symbol": asset.symbol,
        "supply_state": "fixed",
        "supply_base_units": str(
            asset.genesis_supply_base_units
        ),
        "previous_transaction":
            asset.genesis_tx_digest,
    }

    for key, expected_value in expected.items():
        if str(remote.get(key, "")) != str(expected_value):
            raise EconomyAssetSupplyError(
                f"FANZ Sui supply mismatch for {key}."
            )

    currency_object_id = remote.get(
        "currency_object_id"
    )

    if not currency_object_id:
        raise EconomyAssetSupplyError(
            "FANZ Sui supply response has no currency object id."
        )

    with transaction.atomic():
        locked = (
            EconomyAsset.objects
            .select_for_update()
            .get(pk=asset_id)
        )

        if locked.supply_fixed_at:
            return locked, False

        locked.supply_fixed_at = timezone.now()

        metadata = dict(
            locked.metadata or {}
        )

        metadata["currency_object_id"] = (
            currency_object_id
        )

        locked.metadata = metadata

        locked.save(
            update_fields=[
                "supply_fixed_at",
                "metadata",
                "updated_at",
            ]
        )

        return locked, True
