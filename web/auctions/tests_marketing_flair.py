from django.test import SimpleTestCase

from auctions.sunsetcam_cta import (
    CAMPAIGN_ORDER,
    COPY,
    LANGUAGES,
    LABELS,
    DESTINATIONS,
)
from auctions.ai_services.cta_links import labeled_link
from auctions.templatetags.post_content import (
    post_marketing_flair,
    render_post_content,
    render_marketing_content,
)


class MarketingFlairTests(SimpleTestCase):

    def test_all_36_localized_campaign_variants(self):
        for campaign in CAMPAIGN_ORDER:
            for variant in COPY[campaign]:
                for language in LANGUAGES:
                    with self.subTest(
                        campaign=campaign,
                        language=language,
                        message=variant[language],
                    ):
                        message = variant[language]

                        link = labeled_link(
                            LABELS[campaign][language],
                            DESTINATIONS[campaign],
                        )

                        original = message + "\n\n" + link
                        decorated = post_marketing_flair(original)

                        self.assertTrue(
                            decorated.startswith("↳ 💋❤️😘 ")
                        )

                        self.assertTrue(
                            decorated.endswith(
                                "🔥 XOXO 💕\n\n" + link
                            )
                        )

                        self.assertIn(message, decorated)
                        self.assertEqual(decorated.count(link), 1)
                        self.assertEqual(decorated.count("🔥"), 1)

                        self.assertEqual(
                            post_marketing_flair(decorated),
                            decorated,
                        )

                        rendered = str(
                            render_marketing_content(decorated)
                        )

                        self.assertIn(
                            f'href="{DESTINATIONS[campaign]}"',
                            rendered,
                        )

                        self.assertNotIn("fanz-mention", rendered)
                        self.assertNotIn("/auctions/mention/", rendered)

                        self.assertLess(
                            rendered.index("XOXO 💕"),
                            rendered.index(
                                f'href="{DESTINATIONS[campaign]}"'
                            ),
                        )

    def test_marketing_mentions_are_plain_text(self):
        source = "@name @kind @you @it @gone @nombre @nome @tú @você"
        rendered = str(render_marketing_content(source))
        self.assertIn(source, rendered)
        self.assertNotIn("<a ", rendered)

    def test_ordinary_mentions_remain_linked(self):
        rendered = str(render_post_content("Hello @SunsetCam"))
        self.assertIn('class="fanz-mention"', rendered)
        self.assertIn("@SunsetCam</a>", rendered)

    def test_marketing_renderer_retains_link_security(self):
        source = (
            "**Hello** @name "
            "[CTA](/auctions/founder/tienda/) "
            "[Unsafe](javascript:alert%281%29) "
            "https://example.com"
        )
        rendered = str(render_marketing_content(source))
        self.assertIn("<strong>Hello</strong>", rendered)
        self.assertIn('href="/auctions/founder/tienda/"', rendered)
        self.assertIn('href="https://example.com"', rendered)
        self.assertIn('rel="noopener noreferrer ugc"', rendered)
        self.assertNotIn('href="javascript:', rendered)
        self.assertNotIn("fanz-mention", rendered)

    def test_empty_suffix_unchanged(self):
        self.assertEqual(post_marketing_flair(""), "")

    def test_single_paragraph_unchanged(self):
        message = "Ordinary caption ❤️"
        self.assertEqual(
            post_marketing_flair(message),
            message,
        )
