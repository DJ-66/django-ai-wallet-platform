"""Creative DM closers for FANZ-owned fictional AI creators."""

import re

import requests
from django.conf import settings


class CreativeCloserError(RuntimeError):
    pass


def generate_gemma_dm_closer(
    *,
    username,
    bio,
    personality,
    caption,
    recent_closers=(),
    timeout=120,
):
    """Generate one original English DM invitation."""

    if not username or not caption:
        raise CreativeCloserError(
            "Creator and caption are required"
        )

    recent = "\n".join(
        f"- {text}"
        for text in recent_closers
        if text
    )[:1200]

    prompt = f"""
You write as a fictional FANZ AI creator.

Creator: {username}
Bio: {bio}
Personality: {personality}

Current post caption:
{caption}

Write ONE fresh, spontaneous invitation encouraging
followers to send this creator a direct message.

Rules:
- Match the creator's personality and current caption.
- Be playful, conversational, original and human-sounding.
- Use natural humor, teasing or curiosity when appropriate.
- Never reuse the recent closers below.
- Do not claim the creator is a real human.
- Do not promise personal replies, meetings or relationships.
- No URLs, hashtags, @mentions or invented promotions.
- One sentence, maximum 180 characters.
- Return only the invitation.

Recent closers to avoid:
{recent}
""".strip()

    try:
        response = requests.post(
            settings.OLLAMA_URL,
            json={
                "model": "gemma4:12b",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.9,
                    "num_predict": 180,
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()

        closer = (
            response.json()
            .get("message", {})
            .get("content", "")
            .strip()
        )

    except (requests.RequestException, ValueError, KeyError) as exc:
        raise CreativeCloserError(
            "Gemma creative closer generation failed"
        ) from exc

    if (
        not closer
        or len(closer) > 180
        or "\n" in closer
        or re.search(r"https?://|www\.|[#@]", closer)
    ):
        raise CreativeCloserError(
            "Invalid Gemma creative closer"
        )

    if closer.casefold() in {
        text.strip().casefold()
        for text in recent_closers
    }:
        raise CreativeCloserError(
            "Repeated creative closer"
        )

    return closer
