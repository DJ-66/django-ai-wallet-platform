from django.db import transaction

from .models import EconomyAsset
from .sui_adapter import (
    SuiAdapterError,
    get_creator_publication,
)


class EconomyAssetPublicationError(RuntimeError):
    pass


def _expected_module_name(asset):
    return f"{asset.founder_account.handle}_fanz"


def _expected_coin_struct_name(asset):
    return (
        f"{asset.founder_account.handle.upper()}_FANZ"
    )


def _validate_confirmed_publication(
    asset,
    remote_publication,
):
    if remote_publication.get("state") != "confirmed":
        raise EconomyAssetPublicationError(
            "FANZ Sui creator publication is not confirmed."
        )

    expected_chain = asset.chain
    expected_module = _expected_module_name(asset)
    expected_struct = _expected_coin_struct_name(asset)

    if str(remote_publication.get("chain", "")) != expected_chain:
        raise EconomyAssetPublicationError(
            "FANZ Sui publication chain mismatch."
        )

    if (
        str(remote_publication.get("module_name", ""))
        != expected_module
    ):
        raise EconomyAssetPublicationError(
            "FANZ Sui publication module mismatch."
        )

    if (
        str(remote_publication.get("coin_struct_name", ""))
        != expected_struct
    ):
        raise EconomyAssetPublicationError(
            "FANZ Sui publication coin struct mismatch."
        )

    package_id = remote_publication.get("package_id")
    coin_type = remote_publication.get("coin_type")
    tx_digest = remote_publication.get("tx_digest")

    if not package_id:
        raise EconomyAssetPublicationError(
            "Confirmed publication has no package_id."
        )

    if not coin_type:
        raise EconomyAssetPublicationError(
            "Confirmed publication has no coin_type."
        )

    if not tx_digest:
        raise EconomyAssetPublicationError(
            "Confirmed publication has no transaction digest."
        )

    expected_coin_type = (
        f"{package_id}::{expected_module}::{expected_struct}"
    )

    if coin_type != expected_coin_type:
        raise EconomyAssetPublicationError(
            "Confirmed publication coin_type is not canonical."
        )

    return {
        "package_id": package_id,
        "coin_type": coin_type,
        "tx_digest": tx_digest,
    }


def reconcile_confirmed_creator_publication(
    asset_id,
    publication_key,
):
    """
    Write a confirmed FANZ Sui creator publication into EconomyAsset.

    External HTTP happens outside the PostgreSQL transaction.
    The asset row is locked only when applying the validated result.
    """
    asset = (
        EconomyAsset.objects
        .select_related("founder_account")
        .get(pk=asset_id)
    )

    try:
        response = get_creator_publication(
            publication_key
        )
    except SuiAdapterError as exc:
        raise EconomyAssetPublicationError(
            "FANZ Sui publication lookup failed."
        ) from exc

    remote_publication = response.get("publication")

    if not isinstance(remote_publication, dict):
        raise EconomyAssetPublicationError(
            "FANZ Sui response contained no publication object."
        )

    confirmed = _validate_confirmed_publication(
        asset,
        remote_publication,
    )

    with transaction.atomic():
        locked = (
            EconomyAsset.objects
            .select_for_update()
            .select_related("founder_account")
            .get(pk=asset_id)
        )

        # Revalidate against the locked row.
        _validate_confirmed_publication(
            locked,
            remote_publication,
        )

        # Idempotent success path.
        if (
            locked.coin_type == confirmed["coin_type"]
            and locked.genesis_tx_digest
            == confirmed["tx_digest"]
            and locked.metadata.get("package_id")
            == confirmed["package_id"]
            and locked.metadata.get("publication_key")
            == publication_key
        ):
            return locked, False

        # Never overwrite an existing on-chain identity with
        # conflicting publication data.
        if (
            locked.coin_type
            and locked.coin_type != confirmed["coin_type"]
        ):
            raise EconomyAssetPublicationError(
                "EconomyAsset already has a different coin_type."
            )

        if (
            locked.genesis_tx_digest
            and locked.genesis_tx_digest
            != confirmed["tx_digest"]
        ):
            raise EconomyAssetPublicationError(
                "EconomyAsset already has a different genesis transaction."
            )

        metadata = dict(locked.metadata or {})

        existing_package_id = metadata.get("package_id")

        if (
            existing_package_id
            and existing_package_id
            != confirmed["package_id"]
        ):
            raise EconomyAssetPublicationError(
                "EconomyAsset already has a different package_id."
            )

        existing_publication_key = metadata.get(
            "publication_key"
        )

        if (
            existing_publication_key
            and existing_publication_key
            != publication_key
        ):
            raise EconomyAssetPublicationError(
                "EconomyAsset already has a different publication_key."
            )

        metadata["package_id"] = confirmed["package_id"]
        metadata["publication_key"] = publication_key

        locked.coin_type = confirmed["coin_type"]
        locked.genesis_tx_digest = confirmed["tx_digest"]
        locked.metadata = metadata
        locked.status = EconomyAsset.STATUS_ACTIVE

        # Deliberately do NOT set supply_fixed_at here.
        locked.save(
            update_fields=[
                "coin_type",
                "genesis_tx_digest",
                "metadata",
                "status",
                "updated_at",
            ]
        )

        return locked, True

