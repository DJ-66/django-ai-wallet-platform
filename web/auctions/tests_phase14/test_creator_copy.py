import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from auctions.ai_services.creator_copy import (
    CreatorCopyError,
    generate_creator_post_copy,
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
            "AIInfluencer",
            "Fashion",
            "Lifestyle",
            "DigitalCreator",
            "CreatorLife",
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

    @patch(
        "auctions.ai_services.creator_copy.requests.post"
    )
    def test_valid_copy_is_returned(self, post):
        post.return_value = self.response_for({
            "title": "Shadow & Stone",
            "caption": "Strong lines and simple textures.",
            "hashtags": [
                "Fashion",
                "Lifestyle",
                "DigitalCreator",
                "CreatorLife",
            ],
        })

        result = generate_creator_post_copy(
            image_path=self.image_path,
            account="Mandi",
            bio="Creative life.",
            approved_hashtags=self.approved,
        )

        self.assertEqual(
            result["title"],
            "Shadow & Stone",
        )
        self.assertEqual(len(result["hashtags"]), 4)

    @patch(
        "auctions.ai_services.creator_copy.requests.post"
    )
    def test_unapproved_hashtag_is_rejected(self, post):
        post.return_value = self.response_for({
            "title": "Test",
            "caption": "Test caption.",
            "hashtags": [
                "Fashion",
                "Lifestyle",
                "DigitalCreator",
                "California",
            ],
        })

        with self.assertRaises(CreatorCopyError):
            generate_creator_post_copy(
                image_path=self.image_path,
                account="Mandi",
                bio="Creative life.",
                approved_hashtags=self.approved,
            )

    @patch(
        "auctions.ai_services.creator_copy.requests.post"
    )
    def test_malformed_json_is_rejected(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {
                "content": "not json",
            }
        }
        post.return_value = response

        with self.assertRaises(CreatorCopyError):
            generate_creator_post_copy(
                image_path=self.image_path,
                account="Mandi",
                bio="Creative life.",
                approved_hashtags=self.approved,
            )
