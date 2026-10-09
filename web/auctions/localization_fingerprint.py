"""
Deterministic text fingerprint for feed post localization audits.
"""

import hashlib
import json

from .models import FeedPostTranslation


LANGUAGES = ("en", "es", "pt")


def localization_fingerprint(post, *, translations=None):
    """
    Fingerprint canonical post text and all supported translations.

    Always query current translation rows to avoid stale prefetch data.
    Image files are intentionally excluded.
    """
    if translations is None:
        rows = FeedPostTranslation.objects.filter(
            post_id=post.pk,
            language__in=LANGUAGES,
        )
    else:
        rows = translations

    translations = {
        row.language: {
            "title": row.title,
            "content": row.content,
        }
        for row in rows
        if row.language in LANGUAGES
    }

    payload = {
        "title": post.title,
        "content": post.content,
        "translations": {
            language: translations.get(language)
            for language in LANGUAGES
        },
    }

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()
