from django.db import transaction
from django.utils import timezone

from .models import EconomyAssetDelivery
from .economy_asset_custody import (
    EXECUTION_CREATOR_AUTHORIZED,
    EXECUTION_PLATFORM_INVENTORY,
    EconomyAssetCustodyError,
    economy_asset_execution_mode,
)
from .sui_adapter import (
    SuiAdapterConflict,
    SuiAdapterError,
    accept_delivery,
    prepare_delivery,
)


class EconomyDeliveryError(RuntimeError):
    pass


def _validate_adapter_delivery_identity(
    local_delivery,
    remote_delivery,
):
    inventory_address = str(
        (local_delivery.asset.metadata or {}).get(
            "inventory_address"
        ) or ""
    ).strip().lower()

    if not inventory_address:
        raise EconomyDeliveryError(
            "EconomyAsset has no inventory_address."
        )

    expected = {
        "submission_key": str(local_delivery.submission_key),
        "chain": local_delivery.asset.chain,
        "coin_type": local_delivery.asset.coin_type,
        "inventory_address": inventory_address,
        "recipient_address": local_delivery.recipient_address,
        "amount_base_units": str(local_delivery.amount_base_units),
    }

    for key, expected_value in expected.items():
        if str(remote_delivery.get(key, "")) != str(expected_value):
            raise EconomyDeliveryError(
                f"FANZ Sui response mismatch for {key}."
            )

    return remote_delivery


def _validate_adapter_delivery(
    local_delivery,
    remote_delivery,
):
    _validate_adapter_delivery_identity(
        local_delivery,
        remote_delivery,
    )

    if remote_delivery.get("state") != "prepared":
        raise EconomyDeliveryError(
            "FANZ Sui delivery is not in prepared state."
        )

    sender_address = remote_delivery.get(
        "sender_address"
    )

    if not sender_address:
        raise EconomyDeliveryError(
            "FANZ Sui prepared delivery has no sender address."
        )

    return sender_address


def process_pending_economy_delivery(delivery_id):
    """
    Prepare one pending economy delivery through the external FANZ Sui adapter.

    External HTTP occurs outside the database transaction. The row is locked
    only when applying the validated result.
    """
    delivery = (
        EconomyAssetDelivery.objects
        .select_related("asset", "payment_intent")
        .get(pk=delivery_id)
    )

    if delivery.status != EconomyAssetDelivery.STATUS_PENDING:
        return delivery, False

    try:
        execution_mode = economy_asset_execution_mode(
            delivery.asset
        )
    except EconomyAssetCustodyError as exc:
        raise EconomyDeliveryError(
            str(exc)
        ) from exc

    if execution_mode == EXECUTION_CREATOR_AUTHORIZED:
        raise EconomyDeliveryError(
            "Creator-custodied delivery requires "
            "creator-authorized execution."
        )

    if execution_mode != EXECUTION_PLATFORM_INVENTORY:
        raise EconomyDeliveryError(
            "Unsupported economy delivery execution mode."
        )

    try:
        accepted_response = accept_delivery(
            delivery
        )
    except SuiAdapterConflict as exc:
        raise EconomyDeliveryError(
            "FANZ Sui rejected conflicting delivery data."
        ) from exc
    except SuiAdapterError as exc:
        raise EconomyDeliveryError(
            "FANZ Sui adapter unavailable or invalid."
        ) from exc

    accepted_delivery = accepted_response.get(
        "delivery"
    )

    if not isinstance(accepted_delivery, dict):
        raise EconomyDeliveryError(
            "FANZ Sui response contained no delivery object."
        )

    _validate_adapter_delivery_identity(
        delivery,
        accepted_delivery,
    )

    if accepted_delivery.get("state") not in (
        "accepted",
        "prepared",
    ):
        raise EconomyDeliveryError(
            "FANZ Sui delivery is not accepted for preparation."
        )

    try:
        prepared_response = prepare_delivery(
            str(delivery.submission_key)
        )
    except SuiAdapterError as exc:
        raise EconomyDeliveryError(
            "FANZ Sui delivery preparation failed."
        ) from exc

    remote_delivery = prepared_response.get(
        "delivery"
    )

    if not isinstance(remote_delivery, dict):
        raise EconomyDeliveryError(
            "FANZ Sui preparation contained no delivery object."
        )

    sender_address = _validate_adapter_delivery(
        delivery,
        remote_delivery,
    )

    with transaction.atomic():
        locked = (
            EconomyAssetDelivery.objects
            .select_for_update()
            .select_related("asset")
            .get(pk=delivery_id)
        )

        # Another worker may already have advanced it.
        if locked.status != EconomyAssetDelivery.STATUS_PENDING:
            return locked, False

        # Revalidate immutable values after taking the lock.
        _validate_adapter_delivery(
            locked,
            remote_delivery,
        )

        locked.status = EconomyAssetDelivery.STATUS_PREPARED
        locked.sender_address = sender_address
        locked.last_error = ""
        locked.attempt_count += 1

        locked.save(
            update_fields=[
                "status",
                "sender_address",
                "last_error",
                "attempt_count",
                "updated_at",
            ]
        )

        return locked, True


def record_economy_delivery_error(delivery_id, message):
    with transaction.atomic():
        delivery = (
            EconomyAssetDelivery.objects
            .select_for_update()
            .get(pk=delivery_id)
        )

        if delivery.status != EconomyAssetDelivery.STATUS_PENDING:
            return delivery

        delivery.attempt_count += 1
        delivery.last_error = str(message)[:4000]

        delivery.save(
            update_fields=[
                "attempt_count",
                "last_error",
                "updated_at",
            ]
        )

        return delivery
