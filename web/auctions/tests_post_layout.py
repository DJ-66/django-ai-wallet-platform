"""Regression tests for WP03.2 post presentation."""

from types import SimpleNamespace as NS

from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from auctions.sunsetcam_cta import (
    LANGUAGES,
    decorate_sunsetcam_caption,
)
from auctions.templatetags.post_content import (
    post_body,
    post_main_caption,
    post_marketing_suffix,
    post_display_hashtags,
)


class PostLayoutTests(SimpleTestCase):
    caption = "Another beautiful sunset."
    tags = "#Sunset #Beach #FANZ"

    def make_post(self, content, names=(), username="SunsetCam",
                  platform=True, paid=False):
        return NS(
            display_content=content,
            user=NS(
                username=username,
                profile=NS(is_platform_account=platform),
            ),
            is_paid=paid,
            hashtags=NS(
                all=lambda: [NS(name=n) for n in names]
            ),
        )

    def decorated(self, language="en", capture=1):
        return decorate_sunsetcam_caption(
            content=self.caption + "\n\n" + self.tags,
            language=language,
            capture_number=capture,
        )

    def test_multilingual_layout(self):
        layout = Template(
            '{% load post_content %}'
            '{{ post|post_main_caption|render_post_content }}'
            '<div id="test-media">MEDIA</div>'
            '{% include "auctions/includes/_post_marketing_suffix.html" %}'
            '{% include "auctions/includes/_post_hashtags.html" %}'
        )

        for language in LANGUAGES:
            for capture in range(1, 13):
                with self.subTest(language=language, capture=capture):
                    content = self.decorated(language, capture)
                    post = self.make_post(content, ["fanz"])

                    html = layout.render(Context({
                        "post": post,
                        "language": language,
                    }))

                    self.assertEqual(
                        html.count('class="post-marketing-suffix"'), 1
                    )
                    self.assertEqual(
                        html.count('class="post-tags"'), 1
                    )
                    self.assertNotIn("feed-inline-tags", html)

                    self.assertLess(
                        html.index(self.caption),
                        html.index('id="test-media"'),
                    )
                    self.assertLess(
                        html.index('id="test-media"'),
                        html.index('class="post-marketing-suffix"'),
                    )
                    self.assertLess(
                        html.index('class="post-marketing-suffix"'),
                        html.index('class="post-tags"'),
                    )

                    for tag in ("sunset", "beach", "fanz"):
                        self.assertIn(
                            f"/auctions/tag/{tag}/?lang={language}",
                            html,
                        )

                    self.assertEqual(post.display_content, content)

    def test_authorization_boundaries(self):
        content = self.decorated()

        cases = [
            self.make_post(content, username="Creator"),
            self.make_post(content, username="Fanz"),
            self.make_post(content, platform=False),
            self.make_post(content, paid=True),
        ]

        missing_profile = self.make_post(content)
        del missing_profile.user.profile
        cases.append(missing_profile)

        for post in cases:
            with self.subTest(post=post):
                self.assertEqual(post_marketing_suffix(post), "")
                self.assertEqual(
                    post_main_caption(post), post_body(content)
                )

    def test_ordinary_caption_preserved(self):
        content = "Visit our website.\n\n[Click here](/b/create/)"
        post = self.make_post(content)

        self.assertEqual(post_main_caption(post), content)
        self.assertEqual(post_marketing_suffix(post), "")

    def test_hashtag_merge(self):
        post = self.make_post(
            self.caption + "\n\n" + self.tags,
            ["fanz"],
        )

        self.assertEqual(
            post_display_hashtags(post),
            ["fanz", "Sunset", "Beach"],
        )

    def test_hashtag_deduplication(self):
        post = self.make_post(
            "Caption\n\n#Sunset #SUNSET #sunset",
            ["sunset"],
        )

        self.assertEqual(post_display_hashtags(post), ["sunset"])

    def test_discover_fanz_once(self):
        post = self.make_post(
            "Caption\n\n#discover_fanz",
            ["discover_fanz"],
        )

        html = render_to_string(
            "auctions/includes/_post_hashtags.html",
            {"post": post, "language": "en"},
        )

        self.assertEqual(html.count("#discover_fanz"), 1)

    def test_caption_only_hashtags(self):
        post = self.make_post("Caption\n\n#Sunset #FANZ")

        self.assertEqual(
            post_display_hashtags(post), ["Sunset", "FANZ"]
        )

    def test_database_only_hashtags(self):
        post = self.make_post("Caption", ["sunset", "fanz"])

        self.assertEqual(
            post_display_hashtags(post), ["sunset", "fanz"]
        )

    def test_no_empty_hashtag_row(self):
        post = self.make_post("Enjoy the #Sunset tonight.")

        html = render_to_string(
            "auctions/includes/_post_hashtags.html",
            {"post": post, "language": "en"},
        )

        self.assertNotIn('class="post-tags"', html)
        self.assertEqual(post_main_caption(post), post.display_content)
