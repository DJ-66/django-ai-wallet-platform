"""Deterministic suffix selection for FANZ AutoPost."""

from dataclasses import dataclass
from hashlib import sha256


CAMPAIGN_ORDER = (
    "founder",
    "credits",
    "autopost",
    "custom",
)

PERSONALITIES = (
    "flirty",
    "snarky",
    "savage",
    "dominatrix",
)


@dataclass(frozen=True)
class SuffixSelection:
    kind: str
    personality: str
    campaign: str | None
    variant_index: int


def select_suffix(
    *,
    publication_key: str,
    post_number: int,
    cta_every: int,
    personality: str,
    enabled_campaigns: tuple[str, ...],
    variant_count: int,
) -> SuffixSelection:
    """Select one reproducible suffix without modifying state."""
    if not publication_key:
        raise ValueError("publication_key is required")
    if post_number < 1:
        raise ValueError("post_number must be positive")
    if cta_every < 1:
        raise ValueError("cta_every must be positive")
    if personality not in PERSONALITIES:
        raise ValueError("Unknown AutoPost personality")
    if variant_count < 1:
        raise ValueError("At least one variant is required")

    campaigns = tuple(
        name for name in CAMPAIGN_ORDER
        if name in enabled_campaigns
    )

    is_cta = (
        bool(campaigns)
        and post_number % cta_every == 0
    )

    campaign = None
    if is_cta:
        cta_number = post_number // cta_every - 1
        campaign = campaigns[cta_number % len(campaigns)]

    seed = (
        f"{publication_key}|{personality}|"
        f"{campaign or 'organic'}"
    )
    digest = sha256(seed.encode("utf-8")).digest()
    variant_index = int.from_bytes(
        digest[:8], "big"
    ) % variant_count

    return SuffixSelection(
        kind="cta" if is_cta else "personality",
        personality=personality,
        campaign=campaign,
        variant_index=variant_index,
    )
