"""Generate and validate AutoPost drafts without database writes."""

from types import SimpleNamespace

from auctions.ai_services.autopost_assembly import (
    assemble_autopost_translations,
)
from auctions.ai_services.autopost_hashtags import (
    append_autopost_hashtags,
)
from auctions.ai_services.autopost_localization import (
    localize_autopost_draft,
)
from auctions.ai_services.autopost_vision import (
    AutoPostVisionProvider,
)


def generate_autopost_draft(
    *,
    reservation,
    image_bytes,
    hashtags,
    context="",
    vision_provider=None,
    localization_provider=None,
):
    """Return validated EN/ES/PT translations; persist nothing."""

    if reservation.status not in {"reserved", "processing"}:
        raise ValueError("Reservation must be reserved or processing.")

    snapshot = reservation.suffix_translations
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "en", "es", "pt"
    }:
        raise ValueError("Reservation has no frozen suffix.")

    campaign = reservation.campaign
    if campaign and not reservation.destination_url:
        raise ValueError("CTA destination is missing.")
    if not campaign and reservation.destination_url:
        raise ValueError("Personality post has unexpected destination.")

    suffix = SimpleNamespace(
        kind="cta" if campaign else "personality",
        campaign=campaign or None,
        translations=snapshot,
    )

    destination = (
        SimpleNamespace(
            campaign=campaign,
            url=reservation.destination_url,
        )
        if campaign else None
    )

    vision = vision_provider or AutoPostVisionProvider()
    english = vision.generate(
        image_bytes=image_bytes,
        context=context,
    )

    translations = localize_autopost_draft(
        title=english["title"],
        content=english["content"],
        provider=localization_provider,
    )

    translations = append_autopost_hashtags(
        translations=translations,
        hashtags=hashtags,
    )

    return assemble_autopost_translations(
        translations=translations,
        hashtags=hashtags,
        suffix=suffix,
        destination=destination,
    )
