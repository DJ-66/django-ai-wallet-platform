"""Regression tests for multilingual AutoPost suffix composition."""

from django.test import SimpleTestCase

from auctions.ai_services.autopost_composer import (
    compose_autopost_suffix,
)


class AutoPostComposerTests(SimpleTestCase):
    def compose(self, number, **overrides):
        options = {
            "publication_key": f"autopost:test:{number}",
            "post_number": number,
            "cta_every": 3,
            "personality": "snarky",
            "enabled_campaigns": (
                "founder",
                "credits",
                "autopost",
            ),
        }
        options.update(overrides)
        return compose_autopost_suffix(**options)

    def test_regular_regular_cta_rotation(self):
        results = [self.compose(n) for n in range(1, 10)]

        self.assertEqual(
            [r.kind for r in results],
            [
                "personality", "personality", "cta",
                "personality", "personality", "cta",
                "personality", "personality", "cta",
            ],
        )

        self.assertEqual(
            [r.campaign for r in results if r.kind == "cta"],
            ["founder", "credits", "autopost"],
        )

    def test_all_three_languages_present(self):
        for number in range(1, 10):
            result = self.compose(number)
            self.assertEqual(
                set(result.translations),
                {"en", "es", "pt"},
            )
            self.assertTrue(all(result.translations.values()))

    def test_same_publication_produces_same_result(self):
        self.assertEqual(self.compose(6), self.compose(6))

    def test_all_personalities_render(self):
        for personality in (
            "flirty", "snarky", "savage", "dominatrix",
        ):
            result = self.compose(3, personality=personality)
            self.assertEqual(result.kind, "cta")
            self.assertEqual(result.personality, personality)

    def test_disabled_campaign_skipped(self):
        result = self.compose(
            6,
            enabled_campaigns=("founder", "autopost"),
        )
        self.assertEqual(result.campaign, "autopost")

    def test_no_ctas_uses_personality(self):
        result = self.compose(3, enabled_campaigns=())
        self.assertEqual(result.kind, "personality")

    def test_cta_every_post(self):
        campaigns = [
            self.compose(n, cta_every=1).campaign
            for n in (1, 2, 3)
        ]
        self.assertEqual(
            campaigns,
            ["founder", "credits", "autopost"],
        )

    def test_invalid_frequency_rejected(self):
        with self.assertRaises(ValueError):
            self.compose(1, cta_every=0)
