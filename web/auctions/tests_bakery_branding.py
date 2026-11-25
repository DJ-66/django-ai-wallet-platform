from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .fanz_search import _search_destinations


class BakerySearchBrandingTests(SimpleTestCase):

    def test_existing_storefront_route_preserved(self):
        self.assertEqual(
            reverse("founder_tienda"),
            "/auctions/founder/tienda/",
        )

    def test_new_and_legacy_search_aliases(self):
        queries = (
            "fanz bakery",
            "coin bakery",
            "bakery",
            "find your name",
            "find your @name",
            "coin rebrands",
            "founder tienda",
            "founder store",
            "founder shop",
            "tienda",
            "loja founder",
            "mercado founder",
        )

        for query in queries:
            with self.subTest(query=query):
                results = _search_destinations(
                    query,
                    limit=10,
                )

                matches = [
                    result for result in results
                    if result["url"] == reverse("founder_tienda")
                ]

                self.assertEqual(len(matches), 1)
                self.assertEqual(
                    matches[0]["title"],
                    "FANZ Bakery",
                )


class BakeryStorefrontBrandingTests(TestCase):

    def setUp(self):
        self.viewer = get_user_model().objects.create_user(
            username="bakery_branding_viewer",
            password="test-password",
        )
        self.client.force_login(self.viewer)

    def test_storefront_branding_all_languages(self):
        for lang in ("en", "es", "pt"):
            with self.subTest(language=lang):
                response = self.client.get(
                    reverse("founder_tienda"),
                    {"lang": lang},
                    HTTP_ACCEPT_LANGUAGE=lang,
                )

                self.assertEqual(response.status_code, 200)

                self.assertContains(
                    response,
                    "<h1>FANZ Bakery</h1>",
                    count=1,
                )

                self.assertContains(
                    response,
                    "🧁 Coin Bakery",
                    count=2,
                )

                self.assertContains(
                    response,
                    'href="#coin-rebrands"',
                )

                self.assertContains(
                    response,
                    'id="coin-rebrands"',
                )

                self.assertNotContains(
                    response,
                    "<h1>FANZ Founder Tienda</h1>",
                )
