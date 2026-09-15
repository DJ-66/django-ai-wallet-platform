import json
import uuid

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .creator_edge_auth_services import (
    CreatorEdgeAuthError,
    authenticate_and_claim_creator_execution,
    create_creator_edge_auth_challenge,
)


def _json_body(request):
    try:
        value = json.loads(
            request.body.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            "Invalid JSON"
        ) from exc

    if not isinstance(value, dict):
        raise ValueError(
            "JSON body must be an object"
        )

    return value


def _edge_uuid(value):
    try:
        return uuid.UUID(
            str(value or "")
        )
    except (
        ValueError,
        TypeError,
        AttributeError,
    ) as exc:
        raise ValueError(
            "Invalid edge_id"
        ) from exc


@csrf_exempt
@require_POST
def tg_edge_auth_challenge(request):
    try:
        payload = _json_body(request)
        edge_id = _edge_uuid(
            payload.get("edge_id")
        )
    except ValueError as exc:
        return JsonResponse(
            {"error": str(exc)},
            status=400,
        )

    try:
        challenge = (
            create_creator_edge_auth_challenge(
                edge_id=edge_id,
            )
        )
    except CreatorEdgeAuthError as exc:
        return JsonResponse(
            {"error": str(exc)},
            status=403,
        )

    return JsonResponse(
        {
            "challenge_id":
                challenge.pk,
            "edge_id":
                str(challenge.edge.edge_id),
            "message":
                challenge.message,
            "expires_at":
                challenge.expires_at.isoformat(),
        },
        status=201,
    )


@csrf_exempt
@require_POST
def tg_edge_claim_execution(
    request,
    execution_request_id,
):
    try:
        payload = _json_body(request)
        edge_id = _edge_uuid(
            payload.get("edge_id")
        )

        challenge_id = int(
            payload.get("challenge_id")
        )

        if challenge_id <= 0:
            raise ValueError(
                "Invalid challenge_id"
            )

        signature = str(
            payload.get("signature") or ""
        ).strip()

        if not signature:
            raise ValueError(
                "signature is required"
            )

    except (
        ValueError,
        TypeError,
    ) as exc:
        message = (
            str(exc)
            if str(exc)
            else "Invalid request"
        )

        return JsonResponse(
            {"error": message},
            status=400,
        )

    try:
        execution, changed = (
            authenticate_and_claim_creator_execution(
                challenge_id=challenge_id,
                edge_id=edge_id,
                signature=signature,
                execution_request_id=
                    execution_request_id,
            )
        )
    except CreatorEdgeAuthError as exc:
        return JsonResponse(
            {"error": str(exc)},
            status=403,
        )

    delivery = execution.delivery
    asset = delivery.asset

    return JsonResponse(
        {
            "execution_id":
                execution.pk,
            "state":
                execution.status,
            "claimed":
                changed,
            "claim_nonce":
                execution.claim_nonce,
            "coin_type":
                asset.coin_type,
            "custody_address":
                execution.custody_address,
            "recipient_address":
                delivery.recipient_address,
            "amount_base_units":
                str(delivery.amount_base_units),
        }
    )
