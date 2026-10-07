import json
import re

import requests

from django.conf import settings
from django.db import transaction
from langdetect import DetectorFactory, LangDetectException, detect


# Make short social-post language detection deterministic.
DetectorFactory.seed = 0

from .models import FeedPostTranslation


SUPPORTED_LANGUAGES = ("en", "es", "pt")

LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
}


class PostLocalizationError(Exception):
    pass


class LocalizationOllamaProvider:
    """
    FANZ post-localization-specific Ollama provider.

    Localization has its own model setting so changing the translation
    model cannot change AI companion/chat behavior.
    """

    def generate_reply(
        self,
        system_prompt,
        history,
        num_predict=512,
    ):
        payload = {
            "model": settings.FANZ_LOCALIZATION_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                }
            ] + history,
            "stream": False,
            "options": {
                "num_predict": num_predict,
                "temperature": 0.2,
            },
        }

        response = requests.post(
            settings.OLLAMA_URL,
            json=payload,
            timeout=300,
        )

        response.raise_for_status()

        data = response.json()

        return (
            data.get("message", {})
            .get("content", "")
        )


URL_RE = re.compile(
    r"https?://[^\s<>\])]+"
)

MENTION_RE = re.compile(
    r"(?<![\w@])@[A-Za-z0-9_.+-]+"
)

HASHTAG_RE = re.compile(
    r"(?<![\w#])#[A-Za-z0-9_]+"
)


def _extract_json(raw):
    text = (raw or "").strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if (
            start == -1
            or end == -1
            or end <= start
        ):
            raise PostLocalizationError(
                "AI provider did not return JSON."
            )

        try:
            return json.loads(
                text[start:end + 1]
            )
        except json.JSONDecodeError as exc:
            raise PostLocalizationError(
                "AI provider returned invalid JSON."
            ) from exc


def _generate_nonempty(
    provider,
    prompt,
    *,
    num_predict,
    attempts=3,
):
    """
    Localization-only retry wrapper.

    Some local Ollama models occasionally return an empty assistant
    message. Retry only empty responses; provider/network exceptions
    continue to propagate normally.
    """
    for attempt in range(1, attempts + 1):
        raw = provider.generate_reply(
            prompt,
            [],
            num_predict=num_predict,
        )

        text = (raw or "").strip()

        if text:
            return text

    raise PostLocalizationError(
        f"AI provider returned an empty response "
        f"after {attempts} attempts."
    )


def _translation_is_complete(translation):
    return bool(
        translation
        and translation.title.strip()
        and translation.content.strip()
    )


def _translation_is_stale_source_copy(
    translation,
    *,
    post,
    source_language,
):
    """
    A non-source translation that is byte-for-byte identical to the
    canonical source is not a real localization.

    This repairs historical/source-copy rows while preserving genuine
    human translations.
    """
    if not _translation_is_complete(
        translation
    ):
        return False

    if translation.language == source_language:
        return False

    return (
        translation.title == post.title
        and translation.content == post.content
    )


PROTECTED_TOKEN_RE = re.compile(
    r"https?://[^\s<>\])]+"
    r"|(?<![\w@])@[A-Za-z0-9_.+-]+"
    r"|(?<![\w#])#[A-Za-z0-9_]+"
    r"|(?<!\w)(?=[A-Za-z0-9_]*\d)[A-Za-z][A-Za-z0-9_]*(?!\w)"
)


def _mask_protected_tokens(text):
    """
    Replace URLs, mentions and hashtags with opaque placeholders
    before translation.

    The original tokens are restored after AI generation so the
    model never has an opportunity to translate or rewrite them.
    """
    tokens = []

    def replace(match):
        index = len(tokens)
        tokens.append(match.group(0))

        return (
            f"FANZPROTECTEDTOKEN{index}END"
        )

    masked = PROTECTED_TOKEN_RE.sub(
        replace,
        str(text or ""),
    )

    return masked, tokens


def _restore_protected_tokens(
    text,
    tokens,
):
    restored = str(text or "")

    for index, token in enumerate(tokens):
        placeholder = (
            f"FANZPROTECTEDTOKEN{index}END"
        )

        if placeholder not in restored:
            raise PostLocalizationError(
                "AI translation removed or changed "
                f"protected placeholder {index}."
            )

        restored = restored.replace(
            placeholder,
            token,
        )

    # No placeholder should survive restoration.
    if "FANZPROTECTEDTOKEN" in restored:
        raise PostLocalizationError(
            "Unexpected protected placeholder "
            "remained after translation."
        )

    return restored


def _protected_tokens(text):
    source = str(text or "")

    return {
        "urls": sorted(
            URL_RE.findall(source)
        ),
        "mentions": sorted(
            MENTION_RE.findall(source)
        ),
        "hashtags": sorted(
            HASHTAG_RE.findall(source)
        ),
    }


def _validate_preserved_tokens(
    source_text,
    translated_text,
    *,
    language,
):
    source_tokens = _protected_tokens(
        source_text
    )

    translated_tokens = _protected_tokens(
        translated_text
    )

    for kind in (
        "urls",
        "mentions",
        "hashtags",
    ):
        if (
            source_tokens[kind]
            != translated_tokens[kind]
        ):
            raise PostLocalizationError(
                f"{language} translation changed "
                f"protected {kind}: "
                f"{source_tokens[kind]!r} -> "
                f"{translated_tokens[kind]!r}"
            )


def _detect_source_language(post, *, provider=None):
    """
    Detect EN / ES / PT locally.

    AI is deliberately not used for language detection.
    """
    text = " ".join(
        part.strip()
        for part in (
            post.title or "",
            post.content or "",
        )
        if part and part.strip()
    )

    if not text:
        raise PostLocalizationError(
            "Cannot detect language of an empty post."
        )

    try:
        language = detect(text)
    except LangDetectException as exc:
        raise PostLocalizationError(
            "Could not detect source language."
        ) from exc

    # langdetect may return regional-style variants from some
    # inputs. Normalize to FANZ's supported language codes.
    language = (
        language
        .lower()
        .split("-", 1)[0]
    )

    if language not in SUPPORTED_LANGUAGES:
        raise PostLocalizationError(
            f"Unsupported source language: {language!r}"
        )

    return language

def _resolve_source_language(
    post,
    *,
    translations,
    provider=None,
):
    """
    Resolve the canonical post language conservatively.

    A complete translation row whose title/content exactly match the
    canonical post is strong evidence of the source language.

    If exactly one supported language matches, use it directly. This
    avoids unreliable statistical detection for very short posts.

    Multiple or zero matching rows remain ambiguous and fall back to
    local language detection.
    """
    matching_languages = [
        row.language
        for row in translations
        if (
            row.language in SUPPORTED_LANGUAGES
            and _translation_is_complete(row)
            and row.title == post.title
            and row.content == post.content
        )
    ]

    if len(matching_languages) == 1:
        return matching_languages[0]

    return _detect_source_language(
        post,
        provider=provider,
    )


def _translate_target_once(
    post,
    *,
    source_language,
    target_language,
    provider,
):
    """
    Translate title and content independently.

    Plain-text responses are intentionally used instead of JSON so
    longer/link-heavy posts cannot fail because a structured response
    was truncated before its closing JSON syntax.
    """
    target_name = LANGUAGE_NAMES[
        target_language
    ]

    source_name = LANGUAGE_NAMES[
        source_language
    ]

    masked_title, title_tokens = (
        _mask_protected_tokens(
            post.title
        )
    )

    masked_content, content_tokens = (
        _mask_protected_tokens(
            post.content
        )
    )

    title_prompt = f"""
You are a precise localization engine for FANZ.

Translate this social-media post TITLE from {source_name}
into {target_name}.

Rules:
- Preserve meaning and tone.
- Preserve @mentions, hashtags, URLs, emojis, product names,
  proper names and FANZ exactly.
- Do not explain.
- Do not add information.
- Never add @ before a name that did not have @ in the source.
- Never invent a hashtag, mention, URL or link.
- Return ONLY the translated title.

TITLE:
{masked_title}
""".strip()

    title = _generate_nonempty(
        provider,
        title_prompt,
        num_predict=400,
    )

    if not title:
        raise PostLocalizationError(
            f"Empty {target_language} title translation."
        )

    # Strip accidental fenced output without otherwise altering text.
    if title.startswith("```") and title.endswith("```"):
        title = re.sub(
            r"^```(?:text)?\s*",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(
            r"\s*```$",
            "",
            title,
        ).strip()

    title = _restore_protected_tokens(
        title,
        title_tokens,
    )

    content_prompt = f"""
You are a precise localization engine for FANZ.

Translate this social-media post CONTENT from {source_name}
into {target_name}.

STRICT RULES:
- Preserve meaning, tone, formatting, emoji and paragraph breaks.
- Preserve every @mention exactly.
- Preserve every hashtag token exactly. Do not translate hashtags.
- Preserve every URL exactly, including paths, query parameters,
  affiliate/referral codes and fragments.
- For Markdown links [visible text](URL), translate visible text
  naturally when appropriate, but preserve the URL inside parentheses
  exactly.
- Do not explain.
- Do not add information.
- Never add @ before a name that did not have @ in the source.
- Never invent a hashtag, mention, URL or link.
- Return ONLY the translated content.

CONTENT:
{masked_content}
""".strip()

    content = _generate_nonempty(
        provider,
        content_prompt,
        num_predict=1400,
    )

    if not content:
        raise PostLocalizationError(
            f"Empty {target_language} content translation."
        )

    if (
        content.startswith("```")
        and content.endswith("```")
    ):
        content = re.sub(
            r"^```(?:text|markdown)?\s*",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"\s*```$",
            "",
            content,
        ).strip()

    content = _restore_protected_tokens(
        content,
        content_tokens,
    )

    if len(title) > 120:
        raise PostLocalizationError(
            f"{target_language} title exceeds 120 characters."
        )

    if len(content) > 2000:
        raise PostLocalizationError(
            f"{target_language} content exceeds 2000 characters."
        )

    _validate_preserved_tokens(
        post.content,
        content,
        language=target_language,
    )

    return {
        "title": title,
        "content": content,
    }

def _translate_target(
    post,
    *,
    source_language,
    target_language,
    provider,
    attempts=3,
):
    """
    Retry a target translation when AI output violates FANZ
    preservation invariants.

    No unsafe translation is returned or persisted.
    """
    last_error = None

    for _attempt in range(
        1,
        attempts + 1,
    ):
        try:
            return _translate_target_once(
                post,
                source_language=source_language,
                target_language=target_language,
                provider=provider,
            )
        except PostLocalizationError as exc:
            last_error = exc

    raise PostLocalizationError(
        f"{target_language} translation failed safety "
        f"validation after {attempts} attempts: "
        f"{last_error}"
    )


def localize_feed_post(
    post,
    *,
    dry_run=False,
    provider=None,
):
    """
    Populate missing EN/ES/PT FeedPostTranslation rows.

    Complete existing translations are authoritative and are never
    overwritten.
    """
    provider = (
        provider
        or LocalizationOllamaProvider()
    )

    translation_rows = list(
        post.translations.all()
    )

    source_language = (
        _resolve_source_language(
            post,
            translations=translation_rows,
            provider=provider,
        )
    )

    existing_rows = {
        row.language: row
        for row in translation_rows
        if (
            _translation_is_complete(row)
            and not _translation_is_stale_source_copy(
                row,
                post=post,
                source_language=source_language,
            )
        )
    }

    if all(
        language in existing_rows
        for language in SUPPORTED_LANGUAGES
    ):
        return {
            "post_id": post.pk,
            "status": "complete",
            "created": [],
        }

    generated = {}

    for language in SUPPORTED_LANGUAGES:
        if language in existing_rows:
            continue

        if language == source_language:
            generated[language] = {
                "title": post.title,
                "content": post.content,
            }
            continue

        generated[language] = (
            _translate_target(
                post,
                source_language=source_language,
                target_language=language,
                provider=provider,
            )
        )

    if dry_run:
        return {
            "post_id": post.pk,
            "source_language":
                source_language,
            "status": "localized",
            "created": list(
                generated.keys()
            ),
        }

    created_languages = []

    for language, data in generated.items():
        with transaction.atomic():
            translation, _created = (
                FeedPostTranslation.objects
                .select_for_update()
                .get_or_create(
                    post=post,
                    language=language,
                )
            )

            # Someone may have manually filled this while AI was
            # generating. Preserve genuine complete translations, but
            # allow repair of a stale non-source copy.
            if (
                _translation_is_complete(
                    translation
                )
                and not _translation_is_stale_source_copy(
                    translation,
                    post=post,
                    source_language=source_language,
                )
            ):
                continue

            translation.title = data["title"]
            translation.content = (
                data["content"]
            )

            translation.save(
                update_fields=[
                    "title",
                    "content",
                    "updated_at",
                ]
            )

        created_languages.append(
            language
        )

    return {
        "post_id": post.pk,
        "source_language":
            source_language,
        "status": "localized",
        "created": created_languages,
    }
