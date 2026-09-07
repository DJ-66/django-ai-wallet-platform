from django.db import transaction
from django.utils import timezone

from .models import EconomyAsset


class EconomyAssetNetworkPromotionError(RuntimeError):
    pass


@transaction.atomic
def promote_founder_economy_asset_to_mainnet(asset_id):
    """
    Promote one canonical Founder economy asset from its completed
    Testnet identity to a fresh Mainnet publication lifecycle.

    The existing Testnet blockchain asset is never altered. Its
    identity is archived in EconomyAsset.metadata before the canonical
    on-chain fields are reset for Mainnet publication.
    """

    asset = (
        EconomyAsset.objects
        .select_for_update()
        .select_related("founder_account")
        .get(pk=asset_id)
    )

    metadata = dict(asset.metadata or {})

    current_network = str(
        metadata.get("publication_network") or ""
    ).strip().lower()

    if current_network != "testnet":
        raise EconomyAssetNetworkPromotionError(
            "EconomyAsset is not a Testnet publication."
        )

    if asset.status != EconomyAsset.STATUS_ACTIVE:
        raise EconomyAssetNetworkPromotionError(
            "EconomyAsset must be active before Mainnet promotion."
        )

    required_identity = {
        "coin_type": asset.coin_type,
        "genesis_tx_digest": asset.genesis_tx_digest,
        "supply_fixed_at": asset.supply_fixed_at,
        "package_id": metadata.get("package_id"),
        "publication_key": metadata.get("publication_key"),
        "currency_object_id": metadata.get("currency_object_id"),
    }

    missing = [
        key
        for key, value in required_identity.items()
        if not value
    ]

    if missing:
        raise EconomyAssetNetworkPromotionError(
            "EconomyAsset has incomplete Testnet identity: "
            + ", ".join(missing)
        )

    history = list(
        metadata.get("publication_history") or []
    )

    history.append(
        {
            "network": "testnet",
            "publication_key":
                metadata["publication_key"],
            "package_id":
                metadata["package_id"],
            "coin_type":
                asset.coin_type,
            "genesis_tx_digest":
                asset.genesis_tx_digest,
            "currency_object_id":
                metadata["currency_object_id"],
            "supply_fixed_at":
                asset.supply_fixed_at.isoformat(),
            "archived_at":
                timezone.now().isoformat(),
        }
    )

    mainnet_publication_key = (
        f"founder-{asset.pk}-"
        f"{asset.founder_account.handle}-mainnet-v1"
    )

    metadata["publication_history"] = history
    metadata["publication_network"] = "mainnet"
    metadata["publication_key"] = (
        mainnet_publication_key
    )

    # These describe the canonical chain identity and must be
    # repopulated only from a confirmed Mainnet publication.
    metadata.pop("package_id", None)
    metadata.pop("currency_object_id", None)

    asset.coin_type = None
    asset.genesis_tx_digest = None
    asset.supply_fixed_at = None
    asset.status = EconomyAsset.STATUS_DRAFT
    asset.metadata = metadata

    asset.save(
        update_fields=[
            "coin_type",
            "genesis_tx_digest",
            "supply_fixed_at",
            "status",
            "metadata",
            "updated_at",
        ]
    )

    return asset
