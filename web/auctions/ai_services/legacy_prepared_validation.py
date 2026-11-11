"""Validate prepared FANZ AI publication endings."""

from auctions.ai_services.legacy_suffix_assembly import (
    decorate_creator_caption,
)
from auctions.ai_services.legacy_publication_preparation import (
    plan_publication_ending,
)


MARKERS = {
    "ai_gemma4",
    "ai_founder",
    "ai_credits",
    "ai_autopost",
}


def validate_prepared_publication(
    *,
    username,
    publication_key,
    sequence,
    marker,
    content,
):
    """Reject inconsistent or malformed prepared captions."""

    if marker not in MARKERS:
        raise ValueError("Unknown prepared publication marker")

    if not content or "\n\n" not in content:
        raise ValueError("Invalid prepared caption")

    plan = plan_publication_ending(
        username=username,
        publication_key=publication_key,
        sequence=sequence,
    )

    caption, separator, hashtags = content.rpartition("\n\n")

    if (
        not separator
        or not caption.strip()
        or not hashtags.strip()
        or not hashtags.split()[-1] == "#FANZ"
    ):
        raise ValueError("Invalid prepared caption structure")

    if plan.kind == "creative":
        if marker != "ai_gemma4":
            raise ValueError("Creative marker mismatch")

        lines = caption.splitlines()

        if len(lines) < 2 or not lines[-1].strip():
            raise ValueError("Missing creative ending")

    else:
        expected_marker = f"ai_{plan.suffix.campaign}"

        if marker != expected_marker:
            raise ValueError("CTA marker mismatch")

        closer = plan.suffix.translations["en"].strip()
        lines = caption.splitlines()

        if (
            len(lines) < 2
            or lines[-2].strip() != closer
            or lines[-1].strip() != plan.destination.url
        ):
            raise ValueError("Approved CTA ending mismatch")

    if len(content) > 2000:
        raise ValueError("Prepared caption exceeds limit")

    return plan
