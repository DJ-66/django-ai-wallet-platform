from django.db import transaction

from .economy_asset_custody import (
    EXECUTION_CREATOR_AUTHORIZED,
    EconomyAssetCustodyError,
    creator_custody_address,
    economy_asset_execution_mode,
)
from .models import (
    CreatorExecutionRequest,
    EconomyAssetDelivery,
)


class CreatorExecutionError(RuntimeError):
    pass


@transaction.atomic
def get_or_create_creator_execution_request(
    delivery_id,
):
    delivery = (
        EconomyAssetDelivery.objects
        .select_for_update()
        .select_related("asset")
        .get(pk=delivery_id)
    )

    try:
        mode = economy_asset_execution_mode(
            delivery.asset
        )
    except EconomyAssetCustodyError as exc:
        raise CreatorExecutionError(
            str(exc)
        ) from exc

    if mode != EXECUTION_CREATOR_AUTHORIZED:
        raise CreatorExecutionError(
            "Economy delivery is not creator-authorized."
        )

    try:
        custody_address = creator_custody_address(
            delivery.asset
        )
    except EconomyAssetCustodyError as exc:
        raise CreatorExecutionError(
            str(exc)
        ) from exc

    request, created = (
        CreatorExecutionRequest.objects.get_or_create(
            delivery=delivery,
            defaults={
                "custody_address":
                    custody_address,
            },
        )
    )

    if (
        request.custody_address
        != custody_address
    ):
        raise CreatorExecutionError(
            "Creator execution custody address changed."
        )

    return request, created
