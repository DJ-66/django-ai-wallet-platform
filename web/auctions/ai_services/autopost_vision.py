"""Gemma4 image-to-English draft generation for FANZ AutoPost."""

import base64
import json

import requests
from django.conf import settings


class AutoPostVisionError(Exception):
    pass


class AutoPostVisionProvider:
    def generate(self, *, image_bytes, context=""):
        if not image_bytes:
            raise AutoPostVisionError("Image is empty.")

        model = getattr(settings, "FANZ_AUTOPOST_VISION_MODEL", None)
        if not model:
            raise AutoPostVisionError(
                "FANZ_AUTOPOST_VISION_MODEL is not configured."
            )

        prompt = """
You create English social-media captions for FANZ.

Analyze the provided image carefully.
Write an accurate, engaging English title and caption.

Rules:
- Describe only visual details supported by the image.
- Do not invent identities, locations, brands or events.
- Do not add promotional links, hashtags or calls to action.
- Do not include Markdown formatting.
- Keep the title under 120 characters.
- Keep the caption under 1200 characters.
- Return ONLY a JSON object with "title" and "content".

Additional creator context:
""" + (context or "None")

        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [
                    base64.b64encode(image_bytes).decode("ascii")
                ],
            }],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.3,
                "num_predict": 900,
            },
        }

        response = requests.post(
            settings.OLLAMA_URL,
            json=payload,
            timeout=300,
        )
        response.raise_for_status()

        raw = response.json().get("message", {}).get("content", "")

        try:
            result = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise AutoPostVisionError(
                "Gemma4 returned invalid JSON."
            ) from exc

        if not isinstance(result, dict):
            raise AutoPostVisionError("Gemma4 returned invalid draft.")

        title = result.get("title")
        content = result.get("content")

        if not isinstance(title, str) or not title.strip():
            raise AutoPostVisionError("Gemma4 returned an empty title.")

        if not isinstance(content, str) or not content.strip():
            raise AutoPostVisionError("Gemma4 returned an empty caption.")

        title = title.strip()
        content = content.strip()

        if len(title) > 120 or len(content) > 1200:
            raise AutoPostVisionError(
                "Gemma4 draft exceeds configured length limits."
            )

        return {"title": title, "content": content}
