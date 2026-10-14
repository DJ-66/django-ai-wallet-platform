"""Tests for unpublished AutoPost draft localization."""

from django.test import SimpleTestCase

from auctions.ai_services.autopost_localization import (
    localize_autopost_draft,
)
from auctions.post_localization import PostLocalizationError


class FakeProvider:
    def __init__(self):
        self.calls = []

    def generate_reply(self, system_prompt, history, num_predict=512):
        self.calls.append(system_prompt)

        spanish = "into Spanish" in system_prompt

        if "TITLE:" in system_prompt:
            return "Una tarde hermosa" if spanish else "Uma tarde linda"

        return (
            "Una tarde hermosa con FANZ."
            if spanish
            else "Uma tarde linda com FANZ."
        )


class AutoPostLocalizationTests(SimpleTestCase):
    def test_three_languages(self):
        provider = FakeProvider()

        result = localize_autopost_draft(
            title="A beautiful afternoon",
            content="A beautiful afternoon with FANZ.",
            provider=provider,
        )

        self.assertEqual(set(result), {"en", "es", "pt"})
        self.assertEqual(result["en"]["title"], "A beautiful afternoon")
        self.assertEqual(result["es"]["title"], "Una tarde hermosa")
        self.assertEqual(result["pt"]["title"], "Uma tarde linda")
        self.assertEqual(len(provider.calls), 4)

    def test_english_source_preserved(self):
        result = localize_autopost_draft(
            title="  A beautiful afternoon  ",
            content="  A beautiful afternoon with FANZ.  ",
            provider=FakeProvider(),
        )

        self.assertEqual(
            result["en"]["content"],
            "A beautiful afternoon with FANZ.",
        )

    def test_missing_content_rejected(self):
        with self.assertRaises(PostLocalizationError):
            localize_autopost_draft(
                title="A beautiful afternoon",
                content="",
                provider=FakeProvider(),
            )

    def test_oversized_title_rejected(self):
        with self.assertRaises(PostLocalizationError):
            localize_autopost_draft(
                title="A" * 121,
                content="A beautiful afternoon.",
                provider=FakeProvider(),
            )

    def test_rejects_corrupted_protected_url(self):
        class CorruptProvider:
            def generate_reply(
                self, system_prompt, history, num_predict=512
            ):
                if "TITLE:" in system_prompt:
                    return "Una tarde hermosa"

                # Deliberately omit the protected URL placeholder.
                return "Una tarde hermosa sin enlace."

        provider = CorruptProvider()

        with self.assertRaises(PostLocalizationError):
            localize_autopost_draft(
                title="Visit my gallery",
                content="See https://example.com/gallery for photos.",
                provider=provider,
            )
