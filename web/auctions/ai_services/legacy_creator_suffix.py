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


def publication_roll(username, publication_key):
    """Stable 1-5 roll, independently seeded for each creator/post."""
    seed = f"{username.strip().lower()}|{publication_key}"
    digest = sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 5 + 1



def suffix_for_v2_publication(
    *,
    username,
    publication_key,
    sequence,
):
    """Return approved suffix and optional campaign destination."""
    personality = personality_for_creator(username)

    roll = publication_roll(username, publication_key)

    # Stable 60% creative / 40% promotional selection.
    is_cta = roll % 2 == 0

    selected_number = (
        (sequence // CTA_EVERY + 1) * CTA_EVERY
        if is_cta
        else (sequence // CTA_EVERY) * CTA_EVERY + 1
    )

    if is_cta:
        seed = (
            f"{username.strip().lower()}|"
            f"{publication_key}|campaign"
        )
        digest = sha256(seed.encode("utf-8")).digest()
        campaign_index = int.from_bytes(
            digest[:8], "big"
        ) % 4
    else:
        campaign_index = None

    selected_campaign = (
        ("founder", "sponsor", "credits", "autopost")[
            campaign_index
        ]
        if is_cta
        else None
    )

    # Use the shared composer for approved personality copy.
    suffix = compose_autopost_suffix(
        publication_key=publication_key,
        post_number=1,
        cta_every=CTA_EVERY,
        personality=personality,
        enabled_campaigns=CAMPAIGNS,
    )

    if not is_cta:
        return suffix, None

    from auctions.ai_services.autopost_composer import AutoPostSuffix
    from auctions.ai_services.autopost_copy import get_approved_suffix

    if selected_campaign == "sponsor":
        translations = {
            "en": "Support the FANZ platform. Show some love! 💜",
            "es": "Apoya la plataforma FANZ. ¡Comparte tu cariño! 💜",
            "pt": "Apoie a plataforma FANZ. Mostre seu carinho! 💜",
        }
        url = "/Fanz/"
    else:
        translations = {
            language: get_approved_suffix(
                kind="cta",
                personality=personality,
                campaign=selected_campaign,
                language=language,
                variant_index=0,
            )
            for language in ("en", "es", "pt")
        }
        url = resolve_campaign_destination(
            campaign=selected_campaign
        ).url

    from auctions.ai_services.autopost_links import CampaignDestination

    suffix = AutoPostSuffix(
        kind="cta",
        personality=personality,
        campaign=selected_campaign,
        variant_index=0,
        translations=translations,
    )

    destination = CampaignDestination(
        campaign=selected_campaign,
        url=url,
        affiliate_code=None,
    )

    return suffix, destination
