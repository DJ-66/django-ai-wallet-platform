"""Validation and defaults for AutoPost configuration."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from auctions.models import AutoPostConfiguration


class AutoPostConfigurationTests(TestCase):
    def setUp(self):
        self.account = get_user_model().objects.create_user(
            username="autopost_test_account",
        )

    def config(self, **overrides):
        values = {"account": self.account}
        values.update(overrides)
        return AutoPostConfiguration(**values)

    def test_defaults_are_inert(self):
        config = self.config()
        config.full_clean()
        config.save()

        self.assertFalse(config.enabled)
        self.assertEqual(config.personality, "snarky")
        self.assertEqual(config.interval_hours, 36)
        self.assertEqual(config.cta_every, 3)
        self.assertEqual(config.next_sequence, 1)
        self.assertEqual(config.next_media_index, 0)

    def test_valid_custom_campaign(self):
        config = self.config(
            enabled_campaigns=["founder", "credits", "custom"],
            custom_cta_title="Visit my shop",
            custom_cta_url="https://example.com/shop",
        )
        config.full_clean()

    def test_custom_campaign_requires_title_and_url(self):
        for title, url in (
            ("Visit my shop", ""),
            ("", "https://example.com/shop"),
        ):
            with self.subTest(title=title, url=url):
                with self.assertRaises(ValidationError):
                    self.config(
                        enabled_campaigns=["custom"],
                        custom_cta_title=title,
                        custom_cta_url=url,
                    ).full_clean()

    def test_invalid_campaigns_rejected(self):
        for campaigns in (
            ["founder", "founder"],
            ["unknown"],
            [["founder"]],
            "founder",
        ):
            with self.subTest(campaigns=campaigns):
                with self.assertRaises(ValidationError):
                    self.config(
                        enabled_campaigns=campaigns
                    ).full_clean()

    def test_invalid_personality_frequency_and_interval(self):
        for options in (
            {"personality": "unknown"},
            {"cta_every": 0},
            {"cta_every": 11},
            {"interval_hours": 12},
            {"next_sequence": 0},
        ):
            with self.subTest(options=options):
                with self.assertRaises(ValidationError):
                    self.config(**options).full_clean()

    def test_one_configuration_per_account(self):
        self.config().save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.config().save()
