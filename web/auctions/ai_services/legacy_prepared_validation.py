from auctions.ai_services.cta_links import campaign_link, creator_dm_link
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


V2_MARKERS = {
    "ai_v2_gemma4",
    "ai_v2_founder",
    "ai_v2_sponsor",
    "ai_v2_credits",
    "ai_v2_autopost",
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

    if marker in V2_MARKERS:
        return validate_v2_publication(
            username=username,
            publication_key=publication_key,
            sequence=sequence,
            marker=marker,
            content=content,
        )

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


def validate_v2_publication(
    *,
    username,
    publication_key,
    sequence,
    marker,
    content,
):
    """Validate randomized V2 endings and labeled links."""
    from auctions.ai_services.legacy_publication_preparation import (
        plan_v2_publication_ending,
    )

    plan = plan_v2_publication_ending(
        username=username,
        publication_key=publication_key,
        sequence=sequence,
    )

    caption, separator, hashtags = content.rpartition("\n\n")

    if (
        not separator
        or not caption.strip()
        or not hashtags.strip()
        or hashtags.split()[-1] != "#FANZ"
        or len(content) > 2000
    ):
        raise ValueError("Invalid V2 caption structure")

    lines = caption.splitlines()

    if plan.kind == "creative":
        if marker != "ai_v2_gemma4":
            raise ValueError("V2 creative marker mismatch")

        if (
            len(lines) < 3
            or not lines[-3].startswith("↳ 💋❤️😘 ")
            or not lines[-3].endswith(" XOXO 💕")
            or lines[-2].strip()
            or lines[-1].strip() != creator_dm_link(username)
        ):
            raise ValueError("Invalid V2 creative ending")

    else:
        if marker != f"ai_v2_{plan.suffix.campaign}":
            raise ValueError("V2 CTA marker mismatch")

        closer = plan.suffix.translations["en"].strip()

        if (
            len(lines) < 3
            or lines[-3].strip() != (
                "↳ 💋❤️😘 " + closer + " XOXO 💕"
            )
            or lines[-2].strip()
            or lines[-1].strip() != campaign_link(
                plan.suffix.campaign,
                plan.destination,
            )
        ):
            raise ValueError("Invalid V2 CTA ending")

    return plan
