"""AutoPost deterministic hashtag formatting tests."""

from django.test import SimpleTestCase

from auctions.ai_services.autopost_hashtags import (
    append_autopost_hashtags,
)


HASHTAGS = [
    "FANZ", "Creator", "Photography",
    "Lifestyle", "Community", "Explore",
]


class AutoPostHashtagTests(SimpleTestCase):
    def drafts(self):
        return {
            language: {
                "title": "Golden hour",
                "content": f"Beautiful evening in {language}.",
            }
            for language in ("en", "es", "pt")
        }

    def test_appends_identical_six_hashtags(self):
        result = append_autopost_hashtags(
            translations=self.drafts(),
            hashtags=HASHTAGS,
        )

        expected = " ".join(f"#{tag}" for tag in HASHTAGS)

        for language in ("en", "es", "pt"):
            self.assertTrue(
                result[language]["content"].endswith(
                    "\n\n" + expected
                )
            )
            self.assertEqual(
                result[language]["content"].count("\n\n"),
                1,
            )

    def test_does_not_mutate_source(self):
        drafts = self.drafts()

        append_autopost_hashtags(
            translations=drafts,
            hashtags=HASHTAGS,
        )

        self.assertNotIn("#FANZ", drafts["en"]["content"])

    def test_rejects_duplicate_hashtags(self):
        with self.assertRaises(ValueError):
            append_autopost_hashtags(
                translations=self.drafts(),
                hashtags=["FANZ"] * 6,
            )

    def test_rejects_model_generated_hashtags(self):
        drafts = self.drafts()
        drafts["es"]["content"] += " #Invented"

        with self.assertRaises(ValueError):
            append_autopost_hashtags(
                translations=drafts,
                hashtags=HASHTAGS,
            )
