"""Regression tests for FANZ-owned AI creator suffixes."""

from django.test import SimpleTestCase

from auctions.ai_services.legacy_creator_suffix import (
    personality_for_creator,
    suffix_for_publication,
)
from auctions.ai_services.legacy_suffix_assembly import (
    decorate_creator_caption,
)


class LegacyCreatorSuffixTests(SimpleTestCase):

    def test_personality_is_stable(self):
        first = personality_for_creator("Lya")
        second = personality_for_creator("lya")

        self.assertEqual(first, second)

    def test_campaign_rotation(self):
        expected = {
            4: "founder",
            8: "credits",
            12: "autopost",
        }

        for sequence in range(1, 13):
            suffix, destination = suffix_for_publication(
                username="Lya",
                publication_key=f"ai:lya:test:{sequence}",
                sequence=sequence,
            )

            self.assertEqual(
                suffix.campaign,
                expected.get(sequence),
            )

            self.assertEqual(
                set(suffix.translations),
                {"en", "es", "pt"},
            )

            self.assertEqual(
                destination is not None,
                sequence in expected,
            )

    def test_multilingual_assembly(self):
        suffix, destination = suffix_for_publication(
            username="Lya",
            publication_key="ai:lya:multilingual",
            sequence=4,
        )

        for language in ("en", "es", "pt"):
            result = decorate_creator_caption(
                content="Original caption.\n\n#Fashion #FANZ",
                language=language,
                suffix=suffix,
                destination=destination,
            )

            self.assertIn(
                suffix.translations[language],
                result,
            )
            self.assertTrue(
                result.endswith("#Fashion #FANZ")
            )
            self.assertIn(destination.url, result)

    def test_duplicate_suffix_rejected(self):
        suffix, destination = suffix_for_publication(
            username="Lya",
            publication_key="ai:lya:duplicate",
            sequence=1,
        )

        original = "Original caption.\n\n#Fashion #FANZ"

        decorated = decorate_creator_caption(
            content=original,
            language="en",
            suffix=suffix,
            destination=destination,
        )

        with self.assertRaises(ValueError):
            decorate_creator_caption(
                content=decorated,
                language="en",
                suffix=suffix,
                destination=destination,
            )

    def test_retry_determinism(self):
        args = {
            "username": "Lya",
            "publication_key": "ai:lya:retry",
            "sequence": 36,
        }

        self.assertEqual(
            suffix_for_publication(**args),
            suffix_for_publication(**args),
        )
