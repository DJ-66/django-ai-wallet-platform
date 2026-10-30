"""Shared preparation policy for FANZ-owned AI publications."""

from dataclasses import dataclass

from auctions.ai_services.legacy_creator_suffix import (
    personality_for_creator,
    suffix_for_publication,
)


@dataclass(frozen=True)
class PublicationEndingPlan:
    sequence: int
    kind: str
    personality: str
    suffix: object = None
    destination: object = None


def plan_publication_ending(
    *,
    username,
    publication_key,
    sequence,
):
    """Determine the ending without generating or saving content."""

    if not publication_key.startswith("ai:"):
        raise ValueError("Not a FANZ AI publication")

    if sequence < 1:
        raise ValueError("Invalid publication sequence")

    personality = personality_for_creator(username)

    if sequence % 4:
        return PublicationEndingPlan(
            sequence=sequence,
            kind="creative",
            personality=personality,
        )

    suffix, destination = suffix_for_publication(
        username=username,
        publication_key=publication_key,
        sequence=sequence,
    )

    if suffix.kind != "cta" or destination is None:
        raise ValueError("Expected promotional CTA")

    return PublicationEndingPlan(
        sequence=sequence,
        kind="cta",
        personality=personality,
        suffix=suffix,
        destination=destination,
    )
