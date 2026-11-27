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


class BakeryMarketingPresentationTests(SimpleTestCase):
    """WP04.5: localized marketing and price availability."""

    EXPECTED = {'en': ('Premium 1-4 Char @names.',
            'Income-Producing Digital Properties...',
            'As Low As 200 FANZ Credits.',
            'Buy It. Promote It. Re-Sell It. $$$!',
            '— Deeded Virtual Assets —'),
     'es': ('@Nombres Premium de 1 a 4 caracteres.',
            'Propiedades digitales generadoras de ingresos...',
            'Desde solo 200 Créditos FANZ.',
            '¡Compra. Promociona. Revende. $$$!',
            '— Activos Virtuales con Título de Propiedad —'),
     'pt': ('@Nomes Premium de 1 a 4 caracteres.',
            'Propriedades digitais geradoras de renda...',
            'A partir de apenas 200 Créditos FANZ.',
            'Compre. Promova. Revenda. $$$!',
            '— Ativos Virtuais com Título de Propriedade —')}

    def render_marketing(self, language, available):
        from django.template import Context, Template
        from django.template.loader import get_template
        from django.utils.translation import override

        source = get_template(
            "auctions/founder_tienda.html"
        ).template.source

        start = source.index(
            '<div class="founder-marketing">'
        )

        end = source.index("</div>", start) + len("</div>")

        fragment = source[start:end]

        with override(language):
            return Template(
                "{% load i18n %}" + fragment
            ).render(
                Context({
                    "wasteland_listings": (
                        [object()] if available else []
                    ),
                })
            )

    def test_marketing_copy_all_languages_with_inventory(self):
        for language, expected in self.EXPECTED.items():
            with self.subTest(language=language):
                rendered = self.render_marketing(
                    language,
                    available=True,
                )

                for message in expected:
                    self.assertEqual(
                        rendered.count(message),
                        1,
                        message,
                    )

                positions = [
                    rendered.index(message)
                    for message in expected
                ]

                self.assertEqual(
                    positions,
                    sorted(positions),
                )

    def test_price_hidden_when_wasteland_is_sold_out(self):
        for language, expected in self.EXPECTED.items():
            with self.subTest(language=language):
                rendered = self.render_marketing(
                    language,
                    available=False,
                )

                self.assertNotIn(
                    expected[2],
                    rendered,
                )

                self.assertNotIn(
                    'class="founder-marketing-price"',
                    rendered,
                )

                for index in (0, 1, 3, 4):
                    self.assertEqual(
                        rendered.count(expected[index]),
                        1,
                    )

    def test_marketing_styles_remain_scoped(self):
        from django.template.loader import get_template

        source = get_template(
            "auctions/founder_tienda.html"
        ).template.source

        for suffix in (
            "premium",
            "properties",
            "price",
            "action",
            "deed",
        ):
            with self.subTest(style=suffix):
                self.assertIn(
                    ".founder-hero .founder-marketing-"
                    + suffix + " {",
                    source,
                )
