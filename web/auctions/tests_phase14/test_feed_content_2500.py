"""Regression coverage for the 2500-character FANZ feed limit."""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from auctions.models import FeedPost, FeedPostTranslation
from auctions.post_localization import (
    PostLocalizationError,
    _translate_target_once,
)


class FixedProvider:
    def __init__(self, length):
        self.length = length

    def generate_reply(self, system_prompt, history, num_predict=512):
        if "TITLE:" in system_prompt:
            return "Título válido"
        return "A" * self.length


class FeedContentLimitTests(SimpleTestCase):
    def test_model_limits_are_2500(self):
        self.assertEqual(
            FeedPost._meta.get_field("content").max_length,
            2500,
        )
        self.assertEqual(
            FeedPostTranslation._meta.get_field("content").max_length,
            2500,
        )

    def test_2500_character_translation_accepted(self):
        post = FeedPost(
            title="Test title",
            content="A" * 200,
        )

        result = _translate_target_once(
            post,
            source_language="en",
            target_language="es",
            provider=FixedProvider(2500),
        )

        self.assertEqual(len(result["content"]), 2500)

    def test_2501_character_translation_rejected(self):
        post = FeedPost(
            title="Test title",
            content="A" * 200,
        )

        with self.assertRaisesRegex(
            PostLocalizationError,
            "2500 characters",
        ):
            _translate_target_once(
                post,
                source_language="en",
                target_language="es",
                provider=FixedProvider(2501),
            )

    def test_model_validation_rejects_2501(self):
        post = FeedPost(
            title="Test title",
            content="A" * 2501,
        )

        with self.assertRaises(ValidationError):
            post.full_clean()
