"""AutoPost campaign destination regression tests."""

from django.test import SimpleTestCase
from django.urls import reverse

from auctions.ai_services.autopost_links import (
    resolve_campaign_destination,
)


class AutoPostLinkTests(SimpleTestCase):
    def test_founder_destination(self):
        result = resolve_campaign_destination(
            campaign="founder",
            affiliate_code="TESTCODE",
        )
        self.assertEqual(result.url, reverse("founder_tienda"))
        self.assertEqual(result.affiliate_code, "TESTCODE")
        self.assertFalse(result.purchase_attribution_ready)

    def test_credits_destination(self):
        result = resolve_campaign_destination(campaign="credits")
        self.assertEqual(
            result.url,
            reverse(
                "public_profile_root",
                kwargs={"username": "BuyCredits"},
            ),
        )

    def test_autoposter_destination(self):
        result = resolve_campaign_destination(campaign="autopost")
        self.assertEqual(
            result.url,
            reverse(
                "public_profile_root",
                kwargs={"username": "autoPoster"},
            ),
        )

    def test_custom_business_has_no_fanz_affiliate(self):
        result = resolve_campaign_destination(
            campaign="custom",
            custom_url="https://example.com/shop",
            affiliate_code="TESTCODE",
        )
        self.assertEqual(result.url, "https://example.com/shop")
        self.assertIsNone(result.affiliate_code)

    def test_custom_rejects_unsafe_url_forms(self):
        for url in (
            "http://example.com",
            "https://localhost/shop",
            "https://user:password@example.com",
            "https://example.com/#section",
            "javascript:alert(1)",
            "https://example.com/a b",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    resolve_campaign_destination(
                        campaign="custom",
                        custom_url=url,
                    )

    def test_unknown_campaign_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_campaign_destination(campaign="unknown")
