"""Mocked two-stage AutoPost draft pipeline tests."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from auctions.ai_services.autopost_pipeline import (
    generate_autopost_draft,
)


HASHTAGS = [
    "FANZ", "Creator", "Photography",
    "Lifestyle", "Community", "Explore",
]


class FakeVision:
    def generate(self, *, image_bytes, context=""):
        return {
            "title": "Golden hour",
            "content": "Warm evening light over the garden.",
        }


class FakeLocalization:
    def generate_reply(self, system_prompt, history, num_predict=512):
        spanish = "into Spanish" in system_prompt

        if "TITLE:" in system_prompt:
            return "Hora dorada" if spanish else "Hora dourada"

        return (
            "Luz cálida de la tarde sobre el jardín."
            if spanish
            else "Luz quente da tarde sobre o jardim."
        )


class AutoPostPipelineTests(SimpleTestCase):
    def reservation(self):
        return SimpleNamespace(
            status="reserved",
            campaign="",
            destination_url="",
            suffix_translations={
                "en": "Stay curious.",
                "es": "Sigue explorando.",
                "pt": "Continue explorando.",
            },
        )

    def test_complete_three_language_pipeline(self):
        result = generate_autopost_draft(
            reservation=self.reservation(),
            image_bytes=b"test-image",
            hashtags=HASHTAGS,
            vision_provider=FakeVision(),
            localization_provider=FakeLocalization(),
        )

        self.assertEqual(set(result), {"en", "es", "pt"})

        for language in ("en", "es", "pt"):
            content = result[language]["content"]
            self.assertEqual(content.count("\n\n"), 1)
            self.assertIn("#FANZ", content)

        self.assertIn("Stay curious.", result["en"]["content"])
        self.assertIn("Sigue explorando.", result["es"]["content"])

    def test_frozen_cta_destination(self):
        reservation = self.reservation()
        reservation.campaign = "custom"
        reservation.destination_url = "https://example.com/shop"
        reservation.suffix_translations = {
            "en": "Visit my gallery",
            "es": "Visit my gallery",
            "pt": "Visit my gallery",
        }

        result = generate_autopost_draft(
            reservation=reservation,
            image_bytes=b"test-image",
            hashtags=HASHTAGS,
            vision_provider=FakeVision(),
            localization_provider=FakeLocalization(),
        )

        for language in ("en", "es", "pt"):
            self.assertIn(
                "https://example.com/shop",
                result[language]["content"],
            )

    def test_missing_snapshot_rejected(self):
        reservation = self.reservation()
        reservation.suffix_translations = None

        with self.assertRaises(ValueError):
            generate_autopost_draft(
                reservation=reservation,
                image_bytes=b"test-image",
                hashtags=HASHTAGS,
                vision_provider=FakeVision(),
                localization_provider=FakeLocalization(),
            )

    def test_claimed_reservation_can_generate_draft(self):
        reservation = self.reservation()
        reservation.status = "processing"

        result = generate_autopost_draft(
            reservation=reservation,
            image_bytes=b"test-image",
            hashtags=HASHTAGS,
            vision_provider=FakeVision(),
            localization_provider=FakeLocalization(),
        )

        self.assertEqual(set(result), {"en", "es", "pt"})
        self.assertIn("Stay curious.", result["en"]["content"])
