import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from auctions.ai_services.creator_copy import (
    COPY_PROMPT,
    VISION_PROMPT,
    CreatorCopyError,
    generate_creator_post_copy,
)


class CreatorCopyPromptTests(SimpleTestCase):
    def test_vision_prompt_requires_scene_notes(self):
        self.assertIn("private scene notes", VISION_PROMPT.lower())
        self.assertIn("return json only", VISION_PROMPT.lower())

    def test_copy_prompt_requires_creator_personality(self):
        prompt = COPY_PROMPT.lower()
        self.assertIn("fictional", prompt)
        self.assertIn("creator bio", prompt)
        self.assertIn("do not describe", prompt)


@override_settings(
    OLLAMA_MODEL="gemma4:12b",
    CREATOR_VISION_NUM_PREDICT=2048,
    CREATOR_COPY_NUM_PREDICT=2048,
)
class CreatorCopyTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.image_path = (
            Path(self.temp_dir.name) / "image.jpg"
        )
        self.image_path.write_bytes(b"test-image")

        self.approved = [
            "Fashion",
            "Lifestyle",
            "Style",
            "DigitalCreator",
            "Confidence",
        ]

    def response_for(self, data):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {
                "content": json.dumps(data),
            }
        }
        return response

    def vision_response(self):
        return self.response_for({
            "scene": "A fictional creator outdoors.",
            "details": [
                "Outdoor seating",
                "Casual portrait",
            ],
        })

    def copy_response(self):
        return self.response_for({
            "title": "Coffee and Chaos",
            "caption": "One espresso became three.",
            "hashtags": [
                "Fashion",
                "Lifestyle",
                "Style",
                "DigitalCreator",
            ],
        })

    def generate(self):
        return generate_creator_post_copy(
            image_path=self.image_path,
            account="TestCreator",
            bio="Playful fictional creator.",
            approved_hashtags=self.approved,
        )

    @patch(
        "auctions.ai_services.creator_copy.requests.post"
    )
    def test_valid_two_stage_copy(self, post):
        post.side_effect = [
            self.vision_response(),
            self.copy_response(),
        ]

        result = self.generate()

        self.assertEqual(
            result["title"],
            "Coffee and Chaos",
        )
        self.assertEqual(len(result["hashtags"]), 4)
        self.assertEqual(post.call_count, 2)

        vision_payload = post.call_args_list[0].kwargs["json"]
        copy_payload = post.call_args_list[1].kwargs["json"]

        self.assertEqual(
            vision_payload["options"]["num_predict"],
            2048,
        )
        self.assertEqual(
            copy_payload["options"]["num_predict"],
            2048,
        )
        self.assertIs(
            copy_payload["think"],
            False,
        )

    @patch(
        "auctions.ai_services.creator_copy.requests.post"
    )
    def test_unapproved_hashtag_rejected(self, post):
        invalid = self.copy_response()
        invalid.json.return_value["message"]["content"] = (
            json.dumps({
                "title": "Test",
                "caption": "Test caption.",
                "hashtags": [
                    "Fashion",
                    "Lifestyle",
                    "Style",
                    "UnapprovedTag",
                ],
            })
        )

        post.side_effect = [
            self.vision_response(),
            invalid,
        ]

        with self.assertRaises(CreatorCopyError):
            self.generate()

    @patch(
        "auctions.ai_services.creator_copy.requests.post"
    )
    def test_malformed_vision_json_rejected(self, post):
        response = self.vision_response()
        response.json.return_value["message"]["content"] = ""

        post.return_value = response

        with self.assertRaises(CreatorCopyError):
            self.generate()

        self.assertEqual(post.call_count, 1)

    @patch(
        "auctions.ai_services.creator_copy.requests.post"
    )
    def test_malformed_copy_json_rejected(self, post):
        response = self.copy_response()
        response.json.return_value["message"]["content"] = ""

        post.side_effect = [
            self.vision_response(),
            response,
        ]

        with self.assertRaises(CreatorCopyError):
            self.generate()

        self.assertEqual(post.call_count, 2)
