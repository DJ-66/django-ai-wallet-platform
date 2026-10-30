"""Preserve approved multilingual FANZ promotional CTAs."""

from auctions.ai_services.legacy_publication_preparation import (
    plan_publication_ending,
)


def strip_approved_english_cta(
    *,
    content,
    plan,
):
    """Return the original caption without its approved CTA."""

    if plan.kind != "cta":
        return content

    closer = plan.suffix.translations["en"].strip()
    url = plan.destination.url

    caption, separator, hashtags = content.rpartition("\n\n")

    if not separator:
        raise ValueError("Missing caption/hashtag separator")

    ending = "\n" + closer + "\n" + url

    if not caption.endswith(ending):
        raise ValueError("Approved English CTA not found")

    original = caption[:-len(ending)]

    if not original.strip():
        raise ValueError("Original caption is empty")

    return original + "\n\n" + hashtags


def append_approved_localized_cta(
    *,
    content,
    plan,
    language,
):
    """Append the approved CTA without translating its wording."""

    if plan.kind != "cta":
        return content

    if language not in ("en", "es", "pt"):
        raise ValueError("Unsupported language")

    caption, separator, hashtags = content.rpartition("\n\n")

    if not separator:
        raise ValueError("Missing caption/hashtag separator")

    closer = plan.suffix.translations[language].strip()
    url = plan.destination.url

    if not caption.strip() or not closer:
        raise ValueError("Invalid localized caption")

    result = (
        caption
        + "\n"
        + closer
        + "\n"
        + url
        + "\n\n"
        + hashtags
    )

    if len(result) > 2500:
        raise ValueError("Localized caption exceeds limit")

    return result
