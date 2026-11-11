"""Deterministic suffix selection for FANZ-owned AI creators."""

from hashlib import sha256

from auctions.ai_services.autopost_composer import (
    compose_autopost_suffix,
)
from auctions.ai_services.autopost_links import (
    resolve_campaign_destination,
)
from auctions.ai_services.autopost_suffixes import (
    PERSONALITIES,
)

CAMPAIGNS = ("founder", "credits", "autopost")
CTA_EVERY = 4


def personality_for_creator(username):
    """Assign a stable approved personality to a creator."""
    if not username:
        raise ValueError("Creator username is required")

    digest = sha256(
        username.strip().lower().encode("utf-8")
    ).digest()

    index = int.from_bytes(digest[:8], "big") % len(
        PERSONALITIES
    )

    return PERSONALITIES[index]


def suffix_for_publication(
    *,
    username,
    publication_key,
    sequence,
):
    """Return approved suffix and optional campaign destination."""
    personality = personality_for_creator(username)

    suffix = compose_autopost_suffix(
        publication_key=publication_key,
        post_number=sequence,
        cta_every=CTA_EVERY,
        personality=personality,
        enabled_campaigns=CAMPAIGNS,
    )

    destination = (
        resolve_campaign_destination(
            campaign=suffix.campaign,
        )
        if suffix.kind == "cta"
        else None
    )

    return suffix, destination
