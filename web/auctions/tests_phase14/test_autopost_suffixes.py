"""Tests for deterministic FANZ AutoPost suffix selection."""

from django.test import SimpleTestCase

from auctions.ai_services.autopost_suffixes import (
    select_suffix,
)


class AutoPostSuffixTests(SimpleTestCase):
    def select(self, number, **overrides):
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
            "variant_count": 5,
        }
        options.update(overrides)
        return select_suffix(**options)

    def test_regular_regular_cta_pattern(self):
        kinds = [
            self.select(number).kind
            for number in range(1, 10)
        ]
        self.assertEqual(
            kinds,
            [
                "personality", "personality", "cta",
                "personality", "personality", "cta",
                "personality", "personality", "cta",
            ],
        )

    def test_campaigns_rotate(self):
        campaigns = [
            self.select(number).campaign
            for number in (3, 6, 9, 12)
        ]
        self.assertEqual(
            campaigns,
            ["founder", "credits", "autopost", "founder"],
        )

    def test_every_post_can_be_cta(self):
        selections = [
            self.select(number, cta_every=1)
            for number in (1, 2, 3)
        ]
        self.assertEqual(
            [item.campaign for item in selections],
            ["founder", "credits", "autopost"],
        )

    def test_retry_is_deterministic(self):
        first = self.select(6)
        second = self.select(6)
        self.assertEqual(first, second)

    def test_disabled_campaign_is_skipped(self):
        selected = self.select(
            6,
            enabled_campaigns=("founder", "autopost"),
        )
        self.assertEqual(selected.campaign, "autopost")

    def test_no_campaigns_falls_back_to_personality(self):
        selected = self.select(
            3,
            enabled_campaigns=(),
        )
        self.assertEqual(selected.kind, "personality")

    def test_invalid_settings_are_rejected(self):
        with self.assertRaises(ValueError):
            self.select(1, cta_every=0)

        with self.assertRaises(ValueError):
            self.select(1, personality="unknown")
