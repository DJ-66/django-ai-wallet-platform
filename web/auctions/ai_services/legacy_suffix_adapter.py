"""Feature-gated suffix selection for FANZ-owned AI publications."""

import os

from django.db.models import Q

from auctions.ai_services.legacy_creator_suffix import (
    suffix_for_publication,
)
from auctions.models import ScheduledPublication


FLAG = "FANZ_LEGACY_AI_SUFFIX_ENABLED"


def suffix_enabled():
    """Disabled unless explicitly enabled."""
    return os.getenv(FLAG, "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def next_publication_sequence(*, creator_id, scheduled_for):
    """Count earlier AI publications, including failed records."""
    if creator_id is None:
        raise ValueError("Creator is required")

    earlier = ScheduledPublication.objects.filter(
        creator_id=creator_id,
        publication_key__startswith="ai:",
        scheduled_for__lte=scheduled_for,
    ).count()

    return earlier + 1


def publication_sequence(publication):
    """Return the creator's AI publication sequence."""
    if (
        not publication.publication_key.startswith("ai:")
        or publication.creator_id is None
        or publication.pk is None
    ):
        raise ValueError("Invalid AI publication")

    earlier = ScheduledPublication.objects.filter(
        creator_id=publication.creator_id,
        publication_key__startswith="ai:",
    ).filter(
        Q(scheduled_for__lt=publication.scheduled_for)
        | Q(
            scheduled_for=publication.scheduled_for,
            pk__lt=publication.pk,
        )
    ).count()

    return earlier + 1


def suffix_context_for_publication(publication):
    """Select suffix metadata without modifying any records."""
    if not suffix_enabled():
        return None

    if (
        not publication.publication_key.startswith("ai:")
        or publication.media_asset_id is not None
    ):
        return None

    if publication.creator_id is None:
        raise ValueError("AI publication has no creator")

    sequence = publication_sequence(publication)

    suffix, destination = suffix_for_publication(
        username=publication.creator.username,
        publication_key=publication.publication_key,
        sequence=sequence,
    )

    return {
        "sequence": sequence,
        "suffix": suffix,
        "destination": destination,
    }
