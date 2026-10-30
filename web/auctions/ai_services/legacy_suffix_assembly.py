"""Approved suffix assembly for FANZ-owned AI creator captions."""

LANGUAGES = ("en", "es", "pt")
MAX_CONTENT_LENGTH = 2500


def decorate_creator_caption(
    *,
    content,
    language,
    suffix,
    destination=None,
):
    """Insert one approved suffix before the existing hashtag line."""
    if language not in LANGUAGES:
        raise ValueError("Unsupported language")

    if not isinstance(content, str):
        raise ValueError("Caption must be text")

    if "\n\n" not in content:
        raise ValueError("Caption has no hashtag separator")

    caption, hashtag_line = content.rsplit("\n\n", 1)

    if not caption.strip() or not hashtag_line.strip():
        raise ValueError("Caption or hashtag line is empty")

    if not all(
        tag.startswith("#")
        for tag in hashtag_line.split()
    ):
        raise ValueError("Invalid hashtag line")

    closer = suffix.translations[language].strip()

    if not closer or "\n" in closer:
        raise ValueError("Invalid approved suffix")

    if suffix.kind == "cta":
        if destination is None:
            raise ValueError("CTA destination required")
        if destination.campaign != suffix.campaign:
            raise ValueError("CTA campaign mismatch")
        url = destination.url
    elif suffix.kind == "personality":
        if destination is not None:
            raise ValueError("Unexpected CTA destination")
        url = None
    else:
        raise ValueError("Unknown suffix type")

    if closer in [line.strip() for line in caption.splitlines()]:
        raise ValueError("Suffix already applied")

    parts = [caption.strip(), closer]

    if url:
        parts.append(url)

    decorated = "\n".join(parts) + "\n\n" + hashtag_line.strip()

    if len(decorated) > MAX_CONTENT_LENGTH:
        raise ValueError("Decorated caption exceeds 2500 characters")

    return decorated
