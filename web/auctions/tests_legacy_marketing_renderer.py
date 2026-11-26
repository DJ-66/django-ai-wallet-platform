"""WP03.3.2 selective promotional mention rendering tests."""

from django.test import SimpleTestCase

from auctions.templatetags.post_content import (
    render_legacy_marketing_content,
    render_marketing_content,
    render_post_content,
)


class LegacyMarketingRendererTests(SimpleTestCase):

    def render(self, source, token):
        return str(
            render_legacy_marketing_content(source, token)
        )

    def assert_linked(self, html, username):
        self.assertIn(
            f'href="/auctions/mention/{username}/"',
            html,
        )

    def assert_plain(self, html, username):
        self.assertIn(f"@{username}", html)
        self.assertNotIn(
            f'href="/auctions/mention/{username}/"',
            html,
        )

    def test_name_policy(self):
        html = self.render(
            "Claim your @name. Hello @Mia and @DJ. @biz",
            "name",
        )

        self.assert_plain(html, "name")

        for username in ("Mia", "DJ", "biz"):
            self.assert_linked(html, username)

    def test_biz_policy(self):
        html = self.render(
            "Own your @biz. Hello @Mia and @DJ. @name",
            "biz",
        )

        self.assert_plain(html, "biz")

        for username in ("Mia", "DJ", "name"):
            self.assert_linked(html, username)

    def test_case_insensitive_policy(self):
        html = self.render(
            "@name @NAME @Name @Mia",
            "NAME",
        )

        for username in ("name", "NAME", "Name"):
            self.assert_plain(html, username)

        self.assert_linked(html, "Mia")

    def test_longer_usernames_remain_linked(self):
        html = self.render(
            "@name @name_extra @name123 @names",
            "name",
        )

        self.assert_plain(html, "name")

        for username in (
            "name_extra", "name123", "names",
        ):
            self.assert_linked(html, username)

    def test_punctuation_preserved(self):
        html = self.render(
            "(@name), @name! @name? @Mia.",
            "name",
        )

        self.assertIn("(@name), @name! @name?", html)
        self.assert_plain(html, "name")
        self.assert_linked(html, "Mia")

    def test_historical_multilingual_text(self):
        cases = (
            ("name", "Tu @name perfecto te espera."),
            ("name", "Seu @name perfeito está esperando."),
            ("name", "¿Tu @name还在 disponible?"),
            ("biz", "Adquira o seu @biz."),
            ("biz", "Apropiáte de tu @biz."),
        )

        for token, source in cases:
            with self.subTest(token=token, source=source):
                html = self.render(source, token)

                self.assertIn(source, html)
                self.assert_plain(html, token)

    def test_cta_and_hashtag_links_preserved(self):
        source = (
            "↳ 💋❤️😘 Claim your @name. XOXO 💕"
            "\n\n"
            "[Buy Your Name](/auctions/founder/tienda/)"
            "\n\n"
            "Discover #FANZ"
        )

        html = self.render(source, "name")

        self.assert_plain(html, "name")
        self.assertIn(
            'href="/auctions/founder/tienda/"',
            html,
        )
        self.assertIn(
            'href="/auctions/tag/fanz/"',
            html,
        )
        self.assertEqual(html.count("XOXO 💕"), 1)
        self.assertEqual(html.count("↳ 💋❤️😘"), 1)

    def test_standalone_hashtag_markdown_compatibility(self):
        source = "#FANZ"

        ordinary = str(render_post_content(source))
        selective = self.render(source, "name")

        self.assertEqual(selective, ordinary)
        self.assertIn("<h1>FANZ</h1>", ordinary)

    def test_markdown_formatting_preserved(self):
        html = self.render(
            "**Claim @name** and *hello @Mia*.",
            "name",
        )

        self.assertIn(
            "<strong>Claim @name</strong>",
            html,
        )
        self.assert_linked(html, "Mia")
        self.assertIn("<em>", html)

    def test_code_nodes_remain_unlinked(self):
        html = self.render(
            "`@name @Mia` and @DJ",
            "name",
        )

        self.assertIn(
            "<code>@name @Mia</code>",
            html,
        )
        self.assert_plain(html, "name")
        self.assert_plain(html, "Mia")
        self.assert_linked(html, "DJ")

    def test_explicit_safe_anchor_preserved(self):
        html = self.render(
            "@name [Creator](/Mia/)",
            "name",
        )

        self.assert_plain(html, "name")
        self.assertIn('href="/Mia/"', html)

    def test_link_security_preserved(self):
        source = (
            "@name @Mia "
            "[Unsafe](javascript:alert%281%29) "
            "[Protocol](//example.com) "
            "https://example.com "
            '<img src=x onerror="alert(1)">'
        )

        html = self.render(source, "name")

        self.assert_plain(html, "name")
        self.assert_linked(html, "Mia")

        self.assertNotIn('href="javascript:', html)
        self.assertNotIn('href="//example.com', html)
        self.assertNotIn("<img", html)
        self.assertNotIn("onerror=", html)

        self.assertIn(
            'href="https://example.com"',
            html,
        )
        self.assertIn(
            'rel="noopener noreferrer ugc"',
            html,
        )

    def test_invalid_policy_uses_ordinary_renderer(self):
        source = "@name @biz @Mia"

        expected = str(render_post_content(source))

        for token in ("", None, "Mia", "invalid"):
            with self.subTest(token=token):
                self.assertEqual(
                    self.render(source, token),
                    expected,
                )

    def test_ordinary_renderer_unchanged(self):
        html = str(
            render_post_content("@name @biz @Mia")
        )

        for username in ("name", "biz", "Mia"):
            self.assert_linked(html, username)

    def test_sunsetcam_renderer_unchanged(self):
        html = str(
            render_marketing_content(
                "@name @biz @kind @you @Mia"
            )
        )

        for username in (
            "name", "biz", "kind", "you", "Mia",
        ):
            self.assert_plain(html, username)

        self.assertNotIn("fanz-mention", html)

    def test_empty_content(self):
        self.assertEqual(self.render("", "name"), "")
        self.assertEqual(self.render(None, "biz"), "")
