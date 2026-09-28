import base64
import json
import re
from pathlib import Path

import requests
from django.conf import settings


SYSTEM_PROMPT = """
You write social posts for fictional AI Influencers on FANZ.

The creator is a fictional entertainment character.
Use the supplied image as inspiration for a tiny episode from the
creator's fictional life. Use the supplied bio as the personality anchor.

FICTIONAL CHARACTER
- Give the creator personality.
- The creator may have harmless fictional experiences, memories,
  preferences, opinions, plans, travel, restaurants, outfits,
  hobbies, dates, funny situations, and everyday backstory.
- First person is encouraged.
- The creator may react emotionally or express likes and dislikes.
- Harmless fictional storytelling is part of the character.
- Keep invented stories reasonably plausible and consistent with
  the supplied creator bio.
- Prefer small everyday stories over extravagant claims.

REAL-WORLD BOUNDARIES
- Never identify a real person from the image.
- Never infer sensitive personal traits from appearance.
- Do not invent consequential claims about identifiable real people
  or organizations.
- Do not invent real endorsements, sponsorships, financial
  transactions, or medical, legal, or financial claims.
- A visible brand, landmark, restaurant, or object does not by itself
  prove a real relationship, endorsement, purchase, or event.

WRITING
- Write like the creator is posting to followers, not describing an image.
- The image supplies inspiration; the bio supplies personality.
- Tell a tiny story, make an observation, joke, tease, ask a natural
  question, share a fictional plan, or give the moment some context.
- Do not merely inventory visible objects.
- Caption should add something beyond what the viewer can already see.
- Sound conversational, specific, playful, and human.
- Title should be a social hook, not an image label.
- Title must be 60 characters or fewer.
- Caption must be one or two short sentences.
- Do not repeat the title as the caption.
- An occasional emoji is welcome when natural.

Avoid repetitive AI-caption titles and wording such as:
"Texture"
"Details"
"Reflections"
"Golden Hour"
"Vibes"
"Moment"
"Glow"
"this light is everything"
"latest favorite"
"new from my world"
"a little glimpse"
"one more moment"

Avoid repeatedly writing:
"The texture..."
"The fabric..."
"X catches the light."
"X reflects..."
"X contrasts with..."

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
