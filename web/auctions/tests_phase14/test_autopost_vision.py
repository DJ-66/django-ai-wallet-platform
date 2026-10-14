"""Unit tests for AutoPost Gemma4 vision generation."""

from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from auctions.ai_services.autopost_vision import (
    AutoPostVisionError,
    AutoPostVisionProvider,
)


@override_settings(
    FANZ_AUTOPOST_VISION_MODEL="gemma4:test",
    OLLAMA_URL="http://ollama-test/api/chat",
)
class AutoPostVisionTests(SimpleTestCase):
    @patch("auctions.ai_services.autopost_vision.requests.post")
    def test_image_and_model_are_sent(self, post):
        response = Mock()
        response.json.return_value = {
            "message": {
                "content": '{"title":"Golden hour","content":"Warm evening light."}'
            }
        }
        post.return_value = response

        result = AutoPostVisionProvider().generate(
            image_bytes=b"fake-image",
            context="Photography account",
        )

        self.assertEqual(result["title"], "Golden hour")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gemma4:test")
        self.assertTrue(payload["messages"][0]["images"])
        self.assertIn(
            "Photography account",
            payload["messages"][0]["content"],
        )

    @patch("auctions.ai_services.autopost_vision.requests.post")
    def test_invalid_json_is_rejected(self, post):
        response = Mock()
        response.json.return_value = {
            "message": {"content": "not JSON"}
        }
        post.return_value = response

        with self.assertRaises(AutoPostVisionError):
            AutoPostVisionProvider().generate(
                image_bytes=b"fake-image",
            )

    def test_empty_image_is_rejected(self):
        with self.assertRaises(AutoPostVisionError):
            AutoPostVisionProvider().generate(image_bytes=b"")

    @override_settings(FANZ_AUTOPOST_VISION_MODEL="")
    def test_missing_model_is_rejected(self):
        with self.assertRaises(AutoPostVisionError):
            AutoPostVisionProvider().generate(
                image_bytes=b"fake-image",
            )
