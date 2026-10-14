"""Assemble AutoPost suffixes without changing protected hashtags."""

from django.core.management.base import CommandError

from auctions.management.commands.repair_creator_captions import (
    validate_recovery_translations,
)


def assemble_autopost_translations(
    *,
    translations,
    hashtags,
    suffix,
    destination=None,
):
    """Insert one approved suffix before the final hashtag line."""
    validate_recovery_translations(translations, hashtags)

    if set(suffix.translations) != {"en", "es", "pt"}:
        raise ValueError("AutoPost suffix requires EN/ES/PT")

    if suffix.kind == "cta":
        if destination is None:
            raise ValueError("CTA requires a destination")
        if destination.campaign != suffix.campaign:
            raise ValueError("CTA campaign and destination differ")
        url = destination.url
    elif suffix.kind == "personality":
        if destination is not None:
            raise ValueError("Regular post cannot contain CTA destination")
        url = None
    else:
        raise ValueError("Unknown suffix kind")

    result = {}

    for language in ("en", "es", "pt"):
        original = translations[language]
        caption, hashtag_line = original["content"].split("\n\n")

        closer = suffix.translations[language].strip()

        if not closer or "\n" in closer or "\\n" in closer:
            raise ValueError("Invalid AutoPost suffix formatting")

        # Reject reassembly of an already decorated caption.
        # This also protects an existing CTA link from duplication.
        caption_lines = [line.strip() for line in caption.splitlines()]
        if closer in caption_lines:
            raise ValueError("AutoPost suffix already applied")

        parts = [caption, closer]
        if url:
            parts.append(url)

        content = "\n".join(parts) + "\n\n" + hashtag_line

        result[language] = {
            "title": original["title"],
            "content": content,
        }

    # Apply the existing FANZ hashtag and formatting rules again.
    validate_recovery_translations(result, hashtags)

    return result
