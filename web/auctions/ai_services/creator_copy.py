import base64
import json
import re
from pathlib import Path

import requests
from django.conf import settings


SYSTEM_PROMPT = """
You write social posts for fictional digital creators on FANZ.

Write a short creator post inspired by distinctive visible details
in the supplied image and by the supplied creator bio.

GROUNDING
- Never identify a real person.
- Never infer sensitive personal traits from appearance.
- Never invent a real location, event, brand, trip, possession,
  memory, backstory, or activity that is not supplied.
- Do not invent emotions or internal states.
- Keep first-person statements grounded in visible details or
  supplied creator context.

WRITING
- Prefer distinctive visible details over generic lighting/mood.
- Sound conversational and specific.
- Title must be 60 characters or fewer.
- Caption must be one or two short sentences.
- Do not repeat the title as the caption.
- Avoid these phrases:
  "golden hour"
  "vibes"
  "this light is everything"
  "latest favorite"
  "new from my world"
  "a little glimpse"
  "one more moment"

HASHTAGS
- Return exactly 4 hashtags.
- Use only hashtags from the supplied approved hashtag pool.
- Do not include #FANZ.
- Return hashtag names without # characters.

OUTPUT
Return JSON only:
{
  "title": "...",
  "caption": "...",
  "hashtags": ["...", "...", "...", "..."]
}
""".strip()


class CreatorCopyError(RuntimeError):
    pass


def _clean_tag(value):
    value = str(value or "").strip().lstrip("#")

    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise CreatorCopyError(
            f"Invalid generated hashtag: {value!r}"
        )

    return value


def _validate_result(data, approved_hashtags):
    if not isinstance(data, dict):
        raise CreatorCopyError("Model output is not an object.")

    title = str(data.get("title") or "").strip()
    caption = str(data.get("caption") or "").strip()
    hashtags = data.get("hashtags")

    if not title or len(title) > 60:
        raise CreatorCopyError("Invalid generated title.")

    if not caption or len(caption) > 500:
        raise CreatorCopyError("Invalid generated caption.")

    if not isinstance(hashtags, list) or len(hashtags) != 4:
        raise CreatorCopyError(
            "Model must return exactly four hashtags."
        )

    approved = {
        tag.lower(): tag
        for tag in approved_hashtags
    }

    clean_tags = []

    for raw_tag in hashtags:
        tag = _clean_tag(raw_tag)
        canonical = approved.get(tag.lower())

        if canonical is None:
            raise CreatorCopyError(
                f"Unapproved generated hashtag: {tag}"
            )

        if canonical.lower() == "fanz":
            raise CreatorCopyError(
                "Model must not generate FANZ hashtag."
            )

        if canonical.lower() not in {
            item.lower()
            for item in clean_tags
        }:
            clean_tags.append(canonical)

    if len(clean_tags) != 4:
        raise CreatorCopyError(
            "Generated hashtags must be unique."
        )

    return {
        "title": title,
        "caption": caption,
        "hashtags": clean_tags,
    }


def generate_creator_post_copy(
    *,
    image_path,
    account,
    bio,
    approved_hashtags,
    timeout=300,
):
    image_path = Path(image_path)

    if not image_path.is_file():
        raise CreatorCopyError(
            f"Image does not exist: {image_path}"
        )

    image_b64 = base64.b64encode(
        image_path.read_bytes()
    ).decode("ascii")

    context = f"""
Creator: @{account}

BIO:
{bio}

APPROVED HASHTAG POOL:
{", ".join(approved_hashtags)}

Write one FANZ post inspired by the supplied image.
""".strip()

    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": context,
                "images": [image_b64],
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.85,
            "num_predict": 300,
        },
    }

    try:
        response = requests.post(
            settings.OLLAMA_URL,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()

        raw = response.json()["message"]["content"]
        data = json.loads(raw)

        return _validate_result(
            data,
            approved_hashtags,
        )

    except CreatorCopyError:
        raise

    except Exception as exc:
        raise CreatorCopyError(
            f"Creator copy generation failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
