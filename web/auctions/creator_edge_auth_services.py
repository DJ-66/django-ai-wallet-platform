import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    CreatorEdgeAuthChallenge,
    CreatorEdgeRegistration,
    CreatorExecutionRequest,
)


AUTH_CHALLENGE_TTL = timedelta(minutes=5)
AUTH_DOMAIN = "fanz.to"
AUTH_VERSION = "1"


class CreatorEdgeAuthError(RuntimeError):
    pass


def _canonical_auth_message(
    *,
    edge,
    nonce,
    issued_at,
    expires_at,
):
    return "\n".join([
        "FANZ TokenGate Edge Authentication",
        f"version:{AUTH_VERSION}",
        f"domain:{AUTH_DOMAIN}",
        f"edge_id:{edge.edge_id}",
        f"custody_address:{edge.custody_address}",
        f"nonce:{nonce}",
        f"issued_at:{issued_at.isoformat()}",
        f"expires_at:{expires_at.isoformat()}",
    ])


@transaction.atomic
def create_creator_edge_auth_challenge(
    *,
    edge_id,
):
    try:
        edge = (
            CreatorEdgeRegistration.objects
            .select_for_update()
            .get(edge_id=edge_id)
        )
    except CreatorEdgeRegistration.DoesNotExist as exc:
        raise CreatorEdgeAuthError(
            "TG Edge registration does not exist."
        ) from exc

    if (
        edge.status
        != CreatorEdgeRegistration.STATUS_ACTIVE
    ):
        raise CreatorEdgeAuthError(
            "TG Edge registration is not active."
        )

    issued_at = timezone.now()
    expires_at = (
        issued_at + AUTH_CHALLENGE_TTL
    )

    nonce = secrets.token_urlsafe(32)

    message = _canonical_auth_message(
        edge=edge,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    challenge = (
        CreatorEdgeAuthChallenge.objects.create(
            edge=edge,
            nonce=nonce,
            message=message,
            expires_at=expires_at,
        )
    )

    return challenge


@transaction.atomic
def consume_creator_edge_auth_challenge(
    *,
    challenge_id,
    edge_id,
):
    """
    Atomically consume a challenge after cryptographic
    verification has succeeded in the caller.

    This function does not itself verify a Sui signature.
    """
    try:
        challenge = (
            CreatorEdgeAuthChallenge.objects
            .select_for_update()
            .select_related("edge")
            .get(pk=challenge_id)
        )
    except CreatorEdgeAuthChallenge.DoesNotExist as exc:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "does not exist."
        ) from exc

    edge = challenge.edge

    if str(edge.edge_id) != str(edge_id):
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "belongs to another Edge."
        )

    if (
        edge.status
        != CreatorEdgeRegistration.STATUS_ACTIVE
    ):
        raise CreatorEdgeAuthError(
            "TG Edge registration is not active."
        )

    if challenge.consumed_at is not None:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "has already been consumed."
        )

    now = timezone.now()

    if now >= challenge.expires_at:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "has expired."
        )

    challenge.consumed_at = now

    challenge.save(
        update_fields=[
            "consumed_at",
        ]
    )

    return challenge


def authenticate_creator_edge_challenge(
    *,
    challenge_id,
    edge_id,
    signature,
):
    """
    Verify the exact stored challenge against the registered
    creator custody address, then atomically consume it.

    The creator private key never enters FANZ.
    """
    from .sui_adapter import (
        SuiAdapterError,
        verify_personal_message,
    )

    try:
        challenge = (
            CreatorEdgeAuthChallenge.objects
            .select_related("edge")
            .get(pk=challenge_id)
        )
    except CreatorEdgeAuthChallenge.DoesNotExist as exc:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "does not exist."
        ) from exc

    edge = challenge.edge

    if str(edge.edge_id) != str(edge_id):
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "belongs to another Edge."
        )

    if (
        edge.status
        != CreatorEdgeRegistration.STATUS_ACTIVE
    ):
        raise CreatorEdgeAuthError(
            "TG Edge registration is not active."
        )

    if challenge.consumed_at is not None:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "has already been consumed."
        )

    if timezone.now() >= challenge.expires_at:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "has expired."
        )

    try:
        result = verify_personal_message(
            message=challenge.message,
            signature=signature,
            expected_address=edge.custody_address,
        )
    except SuiAdapterError as exc:
        raise CreatorEdgeAuthError(
            "TG Edge wallet signature verification failed."
        ) from exc

    if result.get("valid") is not True:
        raise CreatorEdgeAuthError(
            "TG Edge wallet signature is invalid."
        )

    signer_address = str(
        result.get("signer_address") or ""
    ).strip().lower()

    if signer_address != edge.custody_address.lower():
        raise CreatorEdgeAuthError(
            "TG Edge wallet signer address mismatch."
        )

    return consume_creator_edge_auth_challenge(
        challenge_id=challenge.pk,
        edge_id=edge.edge_id,
    )


def authenticate_and_claim_creator_execution(
    *,
    challenge_id,
    edge_id,
    signature,
    execution_request_id,
):
    """
    Authenticate a creator-operated TG Edge with its Sui wallet
    and atomically consume the one-time authentication challenge
    while claiming one authorized creator execution request.

    External cryptographic verification happens before database
    locks are acquired. After verification succeeds, challenge
    consumption and execution claiming occur in one transaction.
    """
    from .creator_edge_services import (
        CreatorEdgeError,
        authorize_edge_for_execution,
    )
    from .sui_adapter import (
        SuiAdapterError,
        verify_personal_message,
    )

    # ---------------------------------------------------------
    # Prevalidate without holding database locks.
    # ---------------------------------------------------------

    try:
        challenge = (
            CreatorEdgeAuthChallenge.objects
            .select_related("edge")
            .get(pk=challenge_id)
        )
    except CreatorEdgeAuthChallenge.DoesNotExist as exc:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "does not exist."
        ) from exc

    edge = challenge.edge

    if str(edge.edge_id) != str(edge_id):
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "belongs to another Edge."
        )

    if (
        edge.status
        != CreatorEdgeRegistration.STATUS_ACTIVE
    ):
        raise CreatorEdgeAuthError(
            "TG Edge registration is not active."
        )

    if challenge.consumed_at is not None:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "has already been consumed."
        )

    if timezone.now() >= challenge.expires_at:
        raise CreatorEdgeAuthError(
            "TG Edge authentication challenge "
            "has expired."
        )

    try:
        authorize_edge_for_execution(
            edge_id=edge.edge_id,
            execution_request_id=execution_request_id,
        )
    except CreatorEdgeError as exc:
        raise CreatorEdgeAuthError(
            str(exc)
        ) from exc

    # ---------------------------------------------------------
    # Verify Bob's wallet outside the database transaction.
    # ---------------------------------------------------------

    try:
        result = verify_personal_message(
            message=challenge.message,
            signature=signature,
            expected_address=edge.custody_address,
        )
    except SuiAdapterError as exc:
        raise CreatorEdgeAuthError(
            "TG Edge wallet signature verification failed."
        ) from exc

    if result.get("valid") is not True:
        raise CreatorEdgeAuthError(
            "TG Edge wallet signature is invalid."
        )

    signer_address = str(
        result.get("signer_address") or ""
    ).strip().lower()

    if signer_address != edge.custody_address.lower():
        raise CreatorEdgeAuthError(
            "TG Edge wallet signer address mismatch."
        )

    # ---------------------------------------------------------
    # Revalidate under locks, then consume + claim atomically.
    # ---------------------------------------------------------

    with transaction.atomic():
        try:
            locked_challenge = (
                CreatorEdgeAuthChallenge.objects
                .select_for_update(of=("self",))
                .select_related("edge")
                .get(pk=challenge_id)
            )
        except CreatorEdgeAuthChallenge.DoesNotExist as exc:
            raise CreatorEdgeAuthError(
                "TG Edge authentication challenge "
                "does not exist."
            ) from exc

        locked_edge = locked_challenge.edge

        if str(locked_edge.edge_id) != str(edge_id):
            raise CreatorEdgeAuthError(
                "TG Edge authentication challenge "
                "belongs to another Edge."
            )

        if (
            locked_edge.status
            != CreatorEdgeRegistration.STATUS_ACTIVE
        ):
            raise CreatorEdgeAuthError(
                "TG Edge registration is not active."
            )

        if locked_challenge.consumed_at is not None:
            raise CreatorEdgeAuthError(
                "TG Edge authentication challenge "
                "has already been consumed."
            )

        now = timezone.now()

        if now >= locked_challenge.expires_at:
            raise CreatorEdgeAuthError(
                "TG Edge authentication challenge "
                "has expired."
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
            raise CreatorEdgeAuthError(
                "Creator execution request "
                "does not exist."
            ) from exc

        if (
            request.delivery.asset.founder_account_id
            != locked_edge.founder_account_id
        ):
            raise CreatorEdgeAuthError(
                "TG Edge is not authorized for this "
                "creator economy."
            )

        if (
            request.custody_address.strip().lower()
            != locked_edge.custody_address.strip().lower()
        ):
            raise CreatorEdgeAuthError(
                "TG Edge custody address does not match "
                "execution custody."
            )

        edge_identity = str(
            locked_edge.edge_id
        )

        if (
            request.status
            == CreatorExecutionRequest.STATUS_CLAIMED
            and request.claimed_by == edge_identity
            and request.claim_nonce
        ):
            # Authentication challenge is still consumed because
            # this was a valid authenticated idempotent retry.
            locked_challenge.consumed_at = now
            locked_challenge.save(
                update_fields=[
                    "consumed_at",
                ]
            )

            locked_edge.last_seen_at = now
            locked_edge.save(
                update_fields=[
                    "last_seen_at",
                    "updated_at",
                ]
            )

            return request, False

        if (
            request.status
            != CreatorExecutionRequest.STATUS_PENDING
        ):
            raise CreatorEdgeAuthError(
                "Creator execution request "
                "is not claimable."
            )

        import secrets

        request.status = (
            CreatorExecutionRequest.STATUS_CLAIMED
        )
        request.claimed_by = edge_identity
        request.claim_nonce = (
            secrets.token_urlsafe(32)
        )
        request.claimed_at = now
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

        locked_challenge.consumed_at = now
        locked_challenge.save(
            update_fields=[
                "consumed_at",
            ]
        )

        locked_edge.last_seen_at = now
        locked_edge.save(
            update_fields=[
                "last_seen_at",
                "updated_at",
            ]
        )

        return request, True
