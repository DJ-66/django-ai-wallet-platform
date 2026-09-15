from django.db import transaction
from django.utils import timezone

from .economy_asset_custody import (
    EconomyAssetCustodyError,
    creator_custody_address,
)
from .models import (
    CreatorEdgeRegistration,
    CreatorExecutionRequest,
    EconomyAsset,
    FounderAccount,
)


class CreatorEdgeError(RuntimeError):
    pass


def _normalize_address(value):
    return str(value or "").strip().lower()


@transaction.atomic
def register_creator_edge(
    *,
    founder_account_id,
    custody_address,
    label="",
):
    founder = (
        FounderAccount.objects
        .select_for_update()
        .get(pk=founder_account_id)
    )

    try:
        asset = founder.economy_asset
    except EconomyAsset.DoesNotExist as exc:
        raise CreatorEdgeError(
            "Founder account has no economy asset."
        ) from exc

    try:
        expected_custody = creator_custody_address(
            asset
        )
    except EconomyAssetCustodyError as exc:
        raise CreatorEdgeError(
            str(exc)
        ) from exc

    requested_custody = _normalize_address(
        custody_address
    )

    if requested_custody != expected_custody:
        raise CreatorEdgeError(
            "TG Edge custody address does not match "
            "creator economy custody."
        )

    registration = (
        CreatorEdgeRegistration.objects.create(
            founder_account=founder,
            custody_address=expected_custody,
            label=str(label or "").strip()[:120],
        )
    )

    return registration


def authorize_edge_for_execution(
    *,
    edge_id,
    execution_request_id,
):
    try:
        edge = (
            CreatorEdgeRegistration.objects
            .select_related("founder_account")
            .get(edge_id=edge_id)
        )
    except CreatorEdgeRegistration.DoesNotExist as exc:
        raise CreatorEdgeError(
            "TG Edge registration does not exist."
        ) from exc

    if (
        edge.status
        != CreatorEdgeRegistration.STATUS_ACTIVE
    ):
        raise CreatorEdgeError(
            "TG Edge registration is not active."
        )

    try:
        request = (
            CreatorExecutionRequest.objects
            .select_related(
                "delivery__asset__founder_account"
            )
            .get(pk=execution_request_id)
        )
    except CreatorExecutionRequest.DoesNotExist as exc:
        raise CreatorEdgeError(
            "Creator execution request does not exist."
        ) from exc

    founder_id = (
        request.delivery.asset.founder_account_id
    )

    if founder_id != edge.founder_account_id:
        raise CreatorEdgeError(
            "TG Edge is not authorized for this "
            "creator economy."
        )

    if (
        _normalize_address(request.custody_address)
        != _normalize_address(edge.custody_address)
    ):
        raise CreatorEdgeError(
            "TG Edge custody address does not match "
            "execution custody."
        )

    return edge, request


@transaction.atomic
def revoke_creator_edge(edge_id):
    edge = (
        CreatorEdgeRegistration.objects
        .select_for_update()
        .get(edge_id=edge_id)
    )

    if (
        edge.status
        == CreatorEdgeRegistration.STATUS_REVOKED
    ):
        return edge, False

    edge.status = (
        CreatorEdgeRegistration.STATUS_REVOKED
    )
    edge.revoked_at = timezone.now()

    edge.save(
        update_fields=[
            "status",
            "revoked_at",
            "updated_at",
        ]
    )

    return edge, True
