"""Identify published FANZ AI posts carrying approved English suffixes."""

from auctions.ai_services.legacy_suffix_adapter import (
    suffix_context_for_publication,
)


def is_decorated_ai_publication(publication):
    """Check for the exact approved suffix in a linked feed post."""
    if (
        publication is None
        or not publication.publication_key.startswith("ai:")
        or publication.feed_post_id is None
    ):
        return False

    context = suffix_context_for_publication(publication)

    if context is None:
        return False

    suffix = context["suffix"]
    destination = context["destination"]
    content = publication.feed_post.content

    closer = suffix.translations["en"].strip()

    if not closer:
        return False

    caption, separator, _hashtags = content.rpartition("\n\n")

    if not separator:
        return False

    lines = caption.splitlines()

    if suffix.kind == "personality":
        return bool(lines and lines[-1].strip() == closer)

    if suffix.kind == "cta":
        return bool(
            destination is not None
            and len(lines) >= 2
            and lines[-2].strip() == closer
            and lines[-1].strip() == destination.url
        )

    return False
