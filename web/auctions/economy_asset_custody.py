class EconomyAssetCustodyError(RuntimeError):
    pass


EXECUTION_PLATFORM_INVENTORY = "platform_inventory"
EXECUTION_CREATOR_AUTHORIZED = "creator_authorized"


def economy_asset_execution_mode(asset):
    """
    Resolve who is authorized to sign Coin<T> delivery.

    Platform assets may use bounded FANZ inventory.

    Creator assets remain creator-custodied. FANZ records the
    obligation but must not use a FANZ private key to spend the
    creator's Coin<T>.
    """
    metadata = asset.metadata or {}

    issuance_source = str(
        metadata.get("issuance_source") or ""
    ).strip().lower()

    platform_key = str(
        metadata.get("platform_key") or ""
    ).strip().lower()

    if (
        asset.founder_account_id is None
        and issuance_source == "platform"
        and platform_key
    ):
        return EXECUTION_PLATFORM_INVENTORY

    if asset.founder_account_id is not None:
        return EXECUTION_CREATOR_AUTHORIZED

    raise EconomyAssetCustodyError(
        "EconomyAsset custody/execution mode is ambiguous."
    )


def creator_custody_address(asset):
    if (
        economy_asset_execution_mode(asset)
        != EXECUTION_CREATOR_AUTHORIZED
    ):
        raise EconomyAssetCustodyError(
            "EconomyAsset is not creator-custodied."
        )

    address = str(
        (asset.metadata or {}).get(
            "intended_recipient_address"
        ) or ""
    ).strip().lower()

    if not address:
        raise EconomyAssetCustodyError(
            "Creator EconomyAsset has no intended recipient address."
        )

    return address


def platform_inventory_address(asset):
    if (
        economy_asset_execution_mode(asset)
        != EXECUTION_PLATFORM_INVENTORY
    ):
        raise EconomyAssetCustodyError(
            "EconomyAsset is not platform inventory."
        )

    address = str(
        (asset.metadata or {}).get(
            "inventory_address"
        ) or ""
    ).strip().lower()

    if not address:
        raise EconomyAssetCustodyError(
            "Platform EconomyAsset has no inventory_address."
        )

    return address
