"""Prepare a claimed FANZ AI publication outside database locks."""

from auctions.ai_services.legacy_caption_preparation import (
    prepare_ai_caption,
)
from auctions.ai_services.legacy_suffix_adapter import (
    publication_sequence,
)
from auctions.ai_services.legacy_publication_reservation import (
    verify_ai_reservation_claim,
    finalize_claimed_ai_reservation,
    fail_ai_reservation_claim,
)
from auctions.models import ScheduledPublication


def prepare_claimed_ai_publication(
    *,
    reservation_id,
    token,
    bio,
):
    """Generate and finalize a caption for the current lease owner."""

    if not verify_ai_reservation_claim(reservation_id, token):
        return False

    reservation = (
        ScheduledPublication.objects
        .select_related("creator")
        .get(pk=reservation_id)
    )

    sequence = publication_sequence(reservation)

    try:
        prepared, plan = prepare_ai_caption(
            username=reservation.creator.username,
            bio=bio,
            publication_key=reservation.publication_key,
            sequence=sequence,
            content=reservation.content,
        )

        marker = (
            "ai_gemma4"
            if plan.kind == "creative"
            else f"ai_{plan.suffix.campaign}"
        )

        return finalize_claimed_ai_reservation(
            reservation_id=reservation_id,
            token=token,
            content=prepared,
            marker=marker,
        )

    except Exception as exc:
        fail_ai_reservation_claim(
            reservation_id=reservation_id,
            token=token,
            error=exc,
        )
        raise
