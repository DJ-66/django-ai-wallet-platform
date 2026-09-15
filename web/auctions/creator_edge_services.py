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


@transaction.atomic
def claim_creator_execution_request(
    *,
    edge_id,
    execution_request_id,
):
    """
    Atomically claim one creator execution request.

    Authorization is based on the registered Founder economy
    and frozen custody address. Authentication belongs to the
    caller/API layer and is intentionally separate.
    """
    try:
        edge = (
            CreatorEdgeRegistration.objects
            .select_for_update()
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
            .select_for_update(of=("self",))
            .select_related(
                "delivery__asset"
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

    edge_identity = str(edge.edge_id)

    # Idempotent retry from the same Edge.
    if (
        request.status
        == CreatorExecutionRequest.STATUS_CLAIMED
        and request.claimed_by == edge_identity
        and request.claim_nonce
    ):
        return request, False

    if (
        request.status
        != CreatorExecutionRequest.STATUS_PENDING
    ):
        raise CreatorEdgeError(
            "Creator execution request is not claimable."
        )

    request.status = (
        CreatorExecutionRequest.STATUS_CLAIMED
    )
    request.claimed_by = edge_identity

    # Server-generated capability nonce for this exact claim.
    # This is not a wallet credential or private key.
    import secrets
    request.claim_nonce = secrets.token_urlsafe(32)

    request.claimed_at = timezone.now()
    request.last_error = ""

    request.save(
        update_fields=[
            "status",
            "claimed_by",
            "claim_nonce",
            "claimed_at",
            "last_error",
            "updated_at",
        ]
    )

    edge.last_seen_at = timezone.now()
    edge.save(
        update_fields=[
            "last_seen_at",
            "updated_at",
        ]
    )

    return request, True
