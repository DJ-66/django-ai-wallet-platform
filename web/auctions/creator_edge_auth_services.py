import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    CreatorEdgeAuthChallenge,
    CreatorEdgeRegistration,
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
