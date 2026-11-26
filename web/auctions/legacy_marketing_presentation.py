"""Presentation-only recognition of legacy V2 Founder marketing."""

import re
from dataclasses import dataclass

from auctions.ai_services.legacy_prepared_validation import (
    validate_v2_publication,
)
from auctions.models import ScheduledPublication


FOUNDER_MARKER = "ai_v2_founder"
FOUNDER_DESTINATION = "/auctions/founder/tienda/"

PROMOTIONAL_TOKEN_RE = re.compile(
    r"(?<![\w@])@(name|biz)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)

LOCALIZED_PREFIX_RE = re.compile(
    r"^(?:↳|➡️|RedirectTo:?)\s+💋❤️😘(?:\s+|(?=❝))"
)

FOUNDER_LINK_RE = re.compile(
    r"\[([^\[\]\r\n<>@]+)\]"
    r"\(/auctions/founder/tienda/\)"
)


@dataclass(frozen=True)
class LegacyMarketingPresentation:
    caption: str
    suffix: str
    promotional_token: str


def recognize_legacy_founder_marketing(
    *,
    post,
    publication,
    body,
):
    """Recognize authorized legacy marketing without database writes.

    Related objects must be loaded by the presentation service.
    Unrecognized or inconsistent content returns None.
    """
    if post.is_paid or not post.is_public:
        return None

    if publication is None:
        return None

    if (
        publication.status
        != ScheduledPublication.STATUS_PUBLISHED
        or publication.campaign_key != FOUNDER_MARKER
        or not publication.publication_key.startswith("ai:")
        or publication.feed_post_id != post.pk
        or publication.creator_id != post.user_id
        or publication.media_asset_id is not None
        or publication.content != post.content
    ):
        return None

    profile = getattr(post.user, "profile", None)

    if not getattr(profile, "is_platform_account", False):
        return None

    try:
        # V2 currently selects campaign and copy independently
        # of sequence. Do not perform historical COUNT queries.
        plan = validate_v2_publication(
            username=post.user.username,
            publication_key=publication.publication_key,
            sequence=1,
            marker=publication.campaign_key,
            content=post.content,
        )
    except ValueError:
        return None

    if (
        plan.kind != "cta"
        or plan.suffix is None
        or plan.suffix.campaign != "founder"
        or plan.destination is None
        or plan.destination.url != FOUNDER_DESTINATION
    ):
        return None

    approved = plan.suffix.translations["en"]

    tokens = PROMOTIONAL_TOKEN_RE.findall(approved)

    if len(tokens) != 1:
        return None

    token = tokens[0].lower()

    parts = body.rsplit("\n\n", 2)

    if len(parts) != 3:
        return None

    caption, closer, cta = parts

    if (
        not caption.strip()
        or not closer.strip()
        or "\n" in closer
        or "\r" in closer
        or not LOCALIZED_PREFIX_RE.match(closer.lstrip())
        or not FOUNDER_LINK_RE.fullmatch(cta)
    ):
        return None

    displayed_tokens = [
        value.lower()
        for value in PROMOTIONAL_TOKEN_RE.findall(closer)
    ]

    if displayed_tokens != [token]:
        return None

    return LegacyMarketingPresentation(
        caption=caption,
        suffix=closer + "\n\n" + cta,
        promotional_token=token,
    )
