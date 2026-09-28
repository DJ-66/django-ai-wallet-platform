import base64
import json
import re
from pathlib import Path

import requests
from django.conf import settings


VISION_PROMPT = """
Analyze the supplied image only to provide private scene notes
for another writer.

Describe concrete visible elements that could inspire a fictional
social-media story.

Return JSON only:
{
  "scene": "one concise sentence describing the visible setting",
  "details": [
    "visible detail",
    "visible detail",
    "visible detail"
  ]
}

Do not write a social post.
Do not write a title.
Do not invent events, memories, locations, relationships, or backstory.
Do not identify a real person.
Do not infer sensitive personal traits.
Keep the notes concise.
""".strip()


COPY_PROMPT = """
You write social posts AS fictional AI Influencers on FANZ.

You do NOT see the image.
You receive private scene notes produced by a vision system.

IMPORTANT:
The scene notes are inspiration only.
DO NOT rewrite, summarize, describe, or inventory the scene notes.

You ARE the supplied fictional creator.
Imagine the scene notes came from a photo in your fictional life.

Invent a harmless little story around that photo and write what
the creator would actually tell followers.

FICTIONAL CHARACTER
- Invent harmless fictional everyday context freely.
- You may invent your own experiences, memories, preferences,
  opinions, plans, travel, restaurants, outfits, hobbies, dates,
  mishaps, jokes, and backstory.
- First person is strongly preferred.
- Use the creator bio as the personality anchor.
- Prefer believable everyday stories over extravagant claims.
- Give followers personality, humor, curiosity, or something
  worth responding to.

CRITICAL RULE
The follower can already see the photograph.

Do NOT describe:
- fabric
- texture
- lighting
- reflections
- colors
- hair
- poses
- clothing details
- backgrounds
- objects
- scenery

A caption that merely describes the private scene notes is a
FAILED answer.

BAD:
Title: Red Satin Textures
Caption: String lights illuminate the bedding. The controller rests on the surface.

BAD:
Title: Crimson Lace
Caption: The fabric gathers around my hand. Light reflects off the curls.

GOOD:
Title: One More Game 🎮
Caption: I said I'd stop after this round about three rounds ago. Somebody confiscate the controller. 😂

GOOD:
Title: This Was Not the Plan 😂
Caption: I was absolutely going home an hour ago. Then somebody mentioned dessert.

GOOD:
Title: Should I Stay Another Night?
Caption: My suitcase is packed, but Paris is making a very convincing argument.

REAL-WORLD BOUNDARIES
- Do not invent consequential claims about identifiable real people
  or organizations.
- Do not invent real endorsements, sponsorships, financial
  transactions, or medical, legal, or financial claims.
- Do not claim a real person or business interacted with the creator
  unless that information was supplied.

FANZ VOICE
- Sound casual, playful, confident, and internet-native.
- Prefer punchy social writing over polished influencer copy.
- Humor, teasing, mischief, and self-awareness are welcome.
- Short sentence fragments are okay.
- Not every post needs to explain a mood or feeling.
- Not every post needs a question.
- Sometimes simply make a funny, confident, or teasing statement.
- Vary sentence openings and title structures.
- Let the creator bio provide individual personality.

AVOID REPETITIVE FILLER
Do not habitually use:
"vibes"
"feeling..."
"finding my happy place"
"just..."
"seriously..."
"this is everything"
"lost in..."
"soaking up..."
"golden hour"

STYLE
- Title should be a social hook, not an image label.
- Title must be 60 characters or fewer.
- Caption must be one or two short sentences.
- Do not repeat the title in the caption.
- Questions are welcome but not required.
- An occasional emoji is welcome when natural.
- Vary the structure from post to post.

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

    vision_payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": VISION_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "Create private scene notes "
                    "for this image."
                ),
                "images": [image_b64],
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": 180,
        },
    }

    try:
        vision_response = requests.post(
            settings.OLLAMA_URL,
            json=vision_payload,
            timeout=timeout,
        )
        vision_response.raise_for_status()

        vision_raw = (
            vision_response
            .json()["message"]["content"]
        )
        vision_data = json.loads(vision_raw)

        if not isinstance(vision_data, dict):
            raise CreatorCopyError(
                "Vision output is not an object."
            )

        scene = str(
            vision_data.get("scene") or ""
        ).strip()

        details = vision_data.get(
            "details",
            [],
        )

        if not isinstance(details, list):
            details = []

        details = [
            str(item).strip()
            for item in details
            if str(item).strip()
        ][:6]

        if not scene and not details:
            raise CreatorCopyError(
                "Vision returned no scene notes."
            )

        scene_notes = "\n".join(
            [
                f"Scene: {scene}",
                "Visible details:",
                *[
                    f"- {detail}"
                    for detail in details
                ],
            ]
        )

        copy_context = f"""
Creator: @{account}

CREATOR BIO:
{bio}

PRIVATE SCENE NOTES:
{scene_notes}

APPROVED HASHTAG POOL:
{", ".join(approved_hashtags)}

Write the social post now.
Do not describe the scene notes.
""".strip()

        copy_payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": COPY_PROMPT,
                },
                {
                    "role": "user",
                    "content": copy_context,
                },
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.9,
                "num_predict": 300,
            },
        }

        copy_response = requests.post(
            settings.OLLAMA_URL,
            json=copy_payload,
            timeout=timeout,
        )
        copy_response.raise_for_status()

        copy_raw = (
            copy_response
            .json()["message"]["content"]
        )
        copy_data = json.loads(copy_raw)

        return _validate_result(
            copy_data,
            approved_hashtags,
        )

    except CreatorCopyError:
        raise

    except Exception as exc:
        raise CreatorCopyError(
            "Creator copy generation failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
