"""Compose deterministic, multilingual AutoPost suffix selections."""

from dataclasses import dataclass

from auctions.ai_services.autopost_copy import (
    get_approved_suffix,
    get_variant_count,
)
from auctions.ai_services.autopost_suffixes import (
    CAMPAIGN_ORDER,
    select_suffix,
)


LANGUAGES = ("en", "es", "pt")


@dataclass(frozen=True)
class AutoPostSuffix:
    kind: str
    personality: str
    campaign: str | None
    variant_index: int
    translations: dict[str, str]


def compose_autopost_suffix(
    *,
    publication_key: str,
    post_number: int,
    cta_every: int,
    personality: str,
    enabled_campaigns: tuple[str, ...],
) -> AutoPostSuffix:
    """Choose a suffix and its aligned EN/ES/PT variants."""
    if not publication_key:
        raise ValueError("publication_key is required")
    if post_number < 1:
        raise ValueError("post_number must be positive")
    if cta_every < 1:
        raise ValueError("cta_every must be positive")

    campaigns = tuple(
        name for name in CAMPAIGN_ORDER
        if name in enabled_campaigns
    )

    is_cta = bool(campaigns) and post_number % cta_every == 0

    campaign = None
    if is_cta:
        cta_number = post_number // cta_every - 1
        campaign = campaigns[cta_number % len(campaigns)]

    kind = "cta" if is_cta else "personality"

    count = get_variant_count(
        kind=kind,
        personality=personality,
        campaign=campaign,
    )

    selected = select_suffix(
        publication_key=publication_key,
        post_number=post_number,
        cta_every=cta_every,
        personality=personality,
        enabled_campaigns=campaigns,
        variant_count=count,
    )

    translations = {
        language: get_approved_suffix(
            kind=selected.kind,
            personality=selected.personality,
            campaign=selected.campaign,
            language=language,
            variant_index=selected.variant_index,
        )
        for language in LANGUAGES
    }

    return AutoPostSuffix(
        kind=selected.kind,
        personality=selected.personality,
        campaign=selected.campaign,
        variant_index=selected.variant_index,
        translations=translations,
    )
