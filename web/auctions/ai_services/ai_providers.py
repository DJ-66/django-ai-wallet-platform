import requests
from django.conf import settings

class DeepSeekLocalProvider:
    def generate_reply(self, system_prompt, history):
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [{"role": "system", "content": system_prompt}] + history,
            "stream": False,
            "options": {
                "num_predict": 512,
                "temperature": 0.7,
            },
        }

        response = requests.post(
            settings.OLLAMA_URL,
            json=payload,
            timeout=300,
        )

        response.raise_for_status()
        data = response.json()

        return data["message"]["content"]

    def stream_reply(self, system_prompt, history):
        import json

        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [{"role": "system", "content": system_prompt}] + history,
            "stream": True,
            "options": {
                "num_predict": 512,
                "temperature": 0.7,
            },
        }

        response = requests.post(
            settings.OLLAMA_URL,
            json=payload,
            stream=True,
            timeout=300,
        )

        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            chunk = json.loads(line.decode("utf-8"))

            if "message" in chunk and "content" in chunk["message"]:
                yield chunk["message"]["content"]

class OpenAIProvider:
    def generate_reply(self, system_prompt, history):
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=settings.OPENAI_COMPANION_MODEL,
            messages=[{"role": "system", "content": system_prompt}] + history,
            temperature=0.8,
        )

        return response.choices[0].message.content


def get_ai_provider(provider_name):
    if provider_name == "local_deepseek":
        return DeepSeekLocalProvider()

    if provider_name == "openai":
        return OpenAIProvider()

    raise ValueError(f"Unknown provider: {provider_name}")

