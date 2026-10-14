"""Translate unpublished AutoPost drafts without FeedPost writes."""

from types import SimpleNamespace

from auctions.post_localization import (
    LocalizationOllamaProvider,
    PostLocalizationError,
    _translate_target,
)


def localize_autopost_draft(
    *,
    title,
    content,
    provider=None,
):
    """Return EN/ES/PT drafts; persist nothing."""
    if not isinstance(title, str) or not title.strip():
        raise PostLocalizationError("English title is required.")

    if not isinstance(content, str) or not content.strip():
        raise PostLocalizationError("English content is required.")

    if len(title) > 120 or len(content) > 2000:
        raise PostLocalizationError("English draft exceeds FANZ limits.")

    draft = SimpleNamespace(
        title=title.strip(),
        content=content.strip(),
    )

    provider = provider or LocalizationOllamaProvider()

    translations = {
        "en": {
            "title": draft.title,
            "content": draft.content,
        },
    }

    for language in ("es", "pt"):
        translations[language] = _translate_target(
            draft,
            source_language="en",
            target_language=language,
            provider=provider,
        )

    return translations
