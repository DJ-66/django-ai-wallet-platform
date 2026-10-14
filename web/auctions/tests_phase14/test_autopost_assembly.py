"""Tests for safe EN/ES/PT AutoPost caption assembly."""

from django.test import SimpleTestCase

from auctions.ai_services.autopost_assembly import (
    assemble_autopost_translations,
)
from auctions.ai_services.autopost_composer import (
    compose_autopost_suffix,
)
from auctions.ai_services.autopost_links import (
    resolve_campaign_destination,
)


HASHTAGS = [
    "Fashion", "Lifestyle", "Style",
    "Confidence", "AIInfluencer", "FANZ",
]
TAG_LINE = " ".join("#" + tag for tag in HASHTAGS)


class AutoPostAssemblyTests(SimpleTestCase):
    def setUp(self):
        self.translations = {
            lang: {
                "title": title,
                "content": caption + "\n\n" + TAG_LINE,
            }
            for lang, title, caption in (
                ("en", "Beautiful Afternoon", "Beautiful afternoon."),
                ("es", "Hermosa tarde", "Hermosa tarde."),
                ("pt", "Bela tarde", "Bela tarde."),
            )
        }

    def suffix(self, number):
        return compose_autopost_suffix(
            publication_key=f"autopost:test:{number}",
            post_number=number,
            cta_every=3,
            personality="snarky",
            enabled_campaigns=("founder", "credits", "autopost"),
        )

    def test_personality_post_has_no_url(self):
        result = assemble_autopost_translations(
            translations=self.translations,
            hashtags=HASHTAGS,
            suffix=self.suffix(1),
        )
        for data in result.values():
            self.assertEqual(data["content"].count("\n\n"), 1)
            self.assertTrue(data["content"].endswith(TAG_LINE))
            self.assertNotIn("/auctions/founder/tienda/", data["content"])

    def test_founder_cta_has_same_url_in_three_languages(self):
        suffix = self.suffix(3)
        destination = resolve_campaign_destination(
            campaign=suffix.campaign,
            affiliate_code="TESTCODE",
        )
        result = assemble_autopost_translations(
            translations=self.translations,
            hashtags=HASHTAGS,
            suffix=suffix,
            destination=destination,
        )
        for data in result.values():
            self.assertIn(destination.url, data["content"])
            self.assertEqual(data["content"].count("\n\n"), 1)
            self.assertTrue(data["content"].endswith(TAG_LINE))

    def test_cta_requires_destination(self):
        with self.assertRaises(ValueError):
            assemble_autopost_translations(
                translations=self.translations,
                hashtags=HASHTAGS,
                suffix=self.suffix(3),
            )

    def test_rejects_mismatched_campaign(self):
        with self.assertRaises(ValueError):
            assemble_autopost_translations(
                translations=self.translations,
                hashtags=HASHTAGS,
                suffix=self.suffix(3),
                destination=resolve_campaign_destination(
                    campaign="credits",
                ),
            )

    def test_rejects_malformed_hashtags(self):
        broken = {
            lang: dict(data)
            for lang, data in self.translations.items()
        }
        broken["es"]["content"] = (
            "Hermosa tarde.\n\n#Fashion #WrongTag"
        )
        with self.assertRaises(Exception):
            assemble_autopost_translations(
                translations=broken,
                hashtags=HASHTAGS,
                suffix=self.suffix(1),
            )

    def test_repeated_assembly_rejected(self):
        suffix = self.suffix(1)
        first = assemble_autopost_translations(
            translations=self.translations,
            hashtags=HASHTAGS,
            suffix=suffix,
        )
        with self.assertRaises(ValueError):
            assemble_autopost_translations(
                translations=first,
                hashtags=HASHTAGS,
                suffix=suffix,
            )
