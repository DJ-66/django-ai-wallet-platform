from pathlib import Path
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from auctions.ai_services import creator_recovery_generation as generation


HASHTAGS = [
    "Fashion",
    "Lifestyle",
    "Style",
    "Confidence",
    "AIInfluencer",
    "FANZ",
]


def translated(title, caption):
    return {
        "title": title,
        "content": (
            caption + "\n\n"
            + " ".join(f"#{tag}" for tag in HASHTAGS)
        ),
    }


class CreatorRecoveryGenerationTests(SimpleTestCase):
    def setUp(self):
        self.creator = {
            "account": "TestCreator",
            "bio": "A fictional digital creator.",
            "post_style": {
                "hashtags": HASHTAGS[:-1],
            },
        }

        self.generated = {
            "title": "Coffee and Chaos",
            "caption": "One espresso became three.",
            "hashtags": HASHTAGS[:4],
        }

    def test_generates_three_valid_languages(self):
        with (
            patch.object(
                generation,
                "generate_creator_post_copy",
                return_value=self.generated,
            ) as vision,
            patch.object(
                generation,
                "_translate_target",
                side_effect=[
                    translated("Café y caos", "Tres cafés."),
                    translated("Café e caos", "Três cafés."),
                ],
            ) as translate,
        ):
            translations, hashtags = (
                generation.generate_recovery_translations(
                    image_path=Path("/tmp/test.jpg"),
                    creator=self.creator,
                )
            )

        self.assertEqual(hashtags, HASHTAGS)
        self.assertEqual(
            set(translations),
            {"en", "es", "pt"},
        )
        self.assertEqual(vision.call_count, 1)
        self.assertEqual(translate.call_count, 2)

        self.assertEqual(
            [call.kwargs["attempts"] for call in translate.call_args_list],
            [1, 1],
        )

    def test_retries_invalid_spanish_formatting(self):
        malformed = {
            "title": "Café y caos",
            "content": (
                "Tres cafés. "
                + " ".join(f"#{tag}" for tag in HASHTAGS)
            ),
        }

        with (
            patch.object(
                generation,
                "generate_creator_post_copy",
                return_value=self.generated,
            ) as vision,
            patch.object(
                generation,
                "_translate_target",
                side_effect=[
                    malformed,
                    translated("Café y caos", "Tres cafés."),
                    translated("Café e caos", "Três cafés."),
                ],
            ) as translate,
        ):
            translations, hashtags = (
                generation.generate_recovery_translations(
                    image_path=Path("/tmp/test.jpg"),
                    creator=self.creator,
                )
            )

        self.assertEqual(vision.call_count, 1)
        self.assertEqual(translate.call_count, 3)
        self.assertEqual(
            [call.kwargs["target_language"]
             for call in translate.call_args_list],
            ["es", "es", "pt"],
        )
        self.assertEqual(
            translations["en"]["title"],
            "Coffee and Chaos",
        )
        self.assertEqual(set(translations), {"en", "es", "pt"})

    def test_exhausted_formatting_retries_fail(self):
        malformed = {
            "title": "Café y caos",
            "content": "Tres cafés.",
        }

        with (
            patch.object(
                generation,
                "generate_creator_post_copy",
                return_value=self.generated,
            ),
            patch.object(
                generation,
                "_translate_target",
                return_value=malformed,
            ) as translate,
        ):
            with self.assertRaisesRegex(
                CommandError,
                "es recovery formatting failed after 3 attempts",
            ):
                generation.generate_recovery_translations(
                    image_path=Path("/tmp/test.jpg"),
                    creator=self.creator,
                )

        self.assertEqual(translate.call_count, 3)

    def test_retries_protected_token_failure(self):
        from auctions.post_localization import PostLocalizationError

        with (
            patch.object(
                generation,
                "generate_creator_post_copy",
                return_value=self.generated,
            ) as vision,
            patch.object(
                generation,
                "_translate_target",
                side_effect=[
                    PostLocalizationError(
                        "AI translation changed protected placeholder 0."
                    ),
                    translated("Café y caos", "Tres cafés."),
                    translated("Café e caos", "Três cafés."),
                ],
            ) as translate,
        ):
            translations, hashtags = (
                generation.generate_recovery_translations(
                    image_path=Path("/tmp/test.jpg"),
                    creator=self.creator,
                )
            )

        self.assertEqual(vision.call_count, 1)
        self.assertEqual(translate.call_count, 3)
        self.assertEqual(
            [call.kwargs["target_language"]
             for call in translate.call_args_list],
            ["es", "es", "pt"],
        )
        self.assertTrue(
            all(
                call.kwargs["attempts"] == 1
                for call in translate.call_args_list
            )
        )
        self.assertEqual(set(translations), {"en", "es", "pt"})

    def test_rejects_wrong_hashtag_count(self):
        invalid = {
            **self.generated,
            "hashtags": ["Fashion"],
        }

        with patch.object(
            generation,
            "generate_creator_post_copy",
            return_value=invalid,
        ):
            with self.assertRaises(CommandError):
                generation.generate_recovery_translations(
                    image_path=Path("/tmp/test.jpg"),
                    creator=self.creator,
                )

    def test_translation_failure_propagates(self):
        with (
            patch.object(
                generation,
                "generate_creator_post_copy",
                return_value=self.generated,
            ),
            patch.object(
                generation,
                "_translate_target",
                side_effect=RuntimeError(
                    "Translation unavailable"
                ),
            ),
        ):
            with self.assertRaises(RuntimeError):
                generation.generate_recovery_translations(
                    image_path=Path("/tmp/test.jpg"),
                    creator=self.creator,
                )
