"""Multilingual translation for prepared FANZ AI publications."""

from types import SimpleNamespace

from auctions.ai_services.legacy_cta_localization import (
    strip_approved_english_cta,
    append_approved_localized_cta,
)
from auctions.post_localization import (
    PostLocalizationError,
    _translate_target,
    _validate_preserved_tokens,
)


def translate_prepared_ai_post(
    *,
    post,
    plan,
    source_language,
    target_language,
    provider,
):
    """Translate caption once, preserving approved CTA wording."""

    if plan.kind != "cta":
        return _translate_target(
            post,
            source_language=source_language,
            target_language=target_language,
            provider=provider,
        )

    if source_language != "en":
        raise PostLocalizationError(
            "Prepared FANZ CTA source must be English"
        )

    try:
        stripped_content = strip_approved_english_cta(
            content=post.content,
            plan=plan,
        )
    except ValueError as exc:
        raise PostLocalizationError(
            "Invalid approved English CTA"
        ) from exc

    temporary_post = SimpleNamespace(
        title=post.title,
        content=stripped_content,
    )

    translated = _translate_target(
        temporary_post,
        source_language="en",
        target_language=target_language,
        provider=provider,
    )

    try:
        final_content = append_approved_localized_cta(
            content=translated["content"],
            plan=plan,
            language=target_language,
        )
    except ValueError as exc:
        raise PostLocalizationError(
            "Invalid localized FANZ CTA"
        ) from exc

    if len(final_content) > 2500:
        raise PostLocalizationError(
            "Localized FANZ caption exceeds limit"
        )

    _validate_preserved_tokens(
        post.content,
        final_content,
        language=target_language,
    )

    return {
        "title": translated["title"],
        "content": final_content,
    }
