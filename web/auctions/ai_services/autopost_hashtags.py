"""Attach approved FANZ hashtags after draft localization."""

import re

from auctions.management.commands.repair_creator_captions import (
    validate_recovery_translations,
)


def append_autopost_hashtags(*, translations, hashtags):
    if (
        not isinstance(hashtags, (list, tuple))
        or len(hashtags) != 6
        or any(
            not isinstance(tag, str)
            or not re.fullmatch(r"[A-Za-z0-9_]+", tag)
            for tag in hashtags
        )
        or len(set(hashtags)) != 6
    ):
        raise ValueError("Six unique approved hashtags are required.")

    if not isinstance(translations, dict) or set(translations) != {
        "en", "es", "pt"
    }:
        raise ValueError("EN/ES/PT drafts are required.")

    hashtag_line = " ".join(f"#{tag}" for tag in hashtags)
    result = {}

    for language in ("en", "es", "pt"):
        draft = translations[language]
        if not isinstance(draft, dict):
            raise ValueError("Invalid translation draft.")

        title = draft.get("title")
        content = draft.get("content")

        if not isinstance(title, str) or not title.strip():
            raise ValueError("Missing translation title.")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Missing translation caption.")

        title = title.strip()
        content = content.strip()

        if (
            "\n" in content
            or "\\n" in content
            or re.search(r"(?<![\w#])#[A-Za-z0-9_]+", content)
        ):
            raise ValueError(
                "Draft contains paragraph breaks or hashtags."
            )

        result[language] = {
            "title": title,
            "content": content + "\n\n" + hashtag_line,
        }

    validate_recovery_translations(result, hashtags)
    return result
