"""WP03.3.2 persisted legacy marketing integration tests."""

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services.cta_links import campaign_link
from auctions.ai_services.legacy_publication_preparation import (
    plan_v2_publication_ending,
)
from auctions.models import (
    FeedPost,
    FeedPostTranslation,
    ScheduledPublication,
    UserProfile,
)
from auctions.services import prepare_feed_posts
from auctions.templatetags.post_content import (
    post_body,
    post_main_caption,
    post_marketing_suffix,
    render_post_marketing,
)


class LegacyMarketingIntegrationTests(TestCase):

    caption = "Hello @Mia and @DJ. Ordinary @name."
    hashtags = "#Creator #FANZ"
    destination = "/auctions/founder/tienda/"

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.posts = {}

        for token in ("name", "biz"):
            for index in range(1000):
                username = f"WP0332{token}{index}"
                key = f"ai:wp0332:{token}:{index}"

                plan = plan_v2_publication_ending(
                    username=username,
                    publication_key=key,
                    sequence=1,
                )

                if (
                    plan.kind == "cta"
                    and plan.suffix.campaign == "founder"
                    and f"@{token}"
                    in plan.suffix.translations["en"]
                ):
                    break
            else:
                raise AssertionError(
                    "No deterministic Founder fixture"
                )

            user = User.objects.create_user(
                username=username,
            )

            UserProfile.objects.update_or_create(
                user=user,
                defaults={"is_platform_account": True},
            )

            closer = (
                "↳ 💋❤️😘 "
                + plan.suffix.translations["en"]
                + " XOXO 💕"
            )

            cta = campaign_link(
                "founder", plan.destination
            )

            content = (
                cls.caption + "\n\n"
                + closer + "\n\n"
                + cta + "\n\n"
                + cls.hashtags
            )

            post = FeedPost.objects.create(
                user=user,
                title="Legacy Founder fixture",
                content=content,
                is_public=True,
                is_paid=False,
            )

            ScheduledPublication.objects.create(
                creator=user,
                publication_key=key,
                campaign_key="ai_v2_founder",
                content=content,
                scheduled_for=timezone.now(),
                published_at=timezone.now(),
                status="published",
                feed_post=post,
            )

            localized = {
                "en": content,
                "es": (
                    cls.caption + "\n\n"
                    + f" RedirectTo: 💋❤️😘 Tu @{token}. "
                    + "Hola @Mia. Cariñosamente, 😕"
                    + "\n\n"
                    + f"[Comprar tu nombre]({cls.destination})"
                    + "\n\n" + cls.hashtags
                ),
                "pt": (
                    cls.caption + "\n\n"
                    + f"↳ 💋❤️😘❝Garanta seu @{token}.❞ "
                    + "XOXO 💕"
                    + "\n\n"
                    + f"[Compre Seu Nome]({cls.destination})"
                    + "\n\n" + cls.hashtags
                ),
            }

            for language, value in localized.items():
                FeedPostTranslation.objects.create(
                    post=post,
                    language=language,
                    title=post.title,
                    content=value,
                )

            cls.posts[token] = post.pk

    def prepare(self, token="name", language="en"):
        return prepare_feed_posts(
            FeedPost.objects.filter(
                pk=self.posts[token]
            ),
            language=language,
        )[0]

    def render_layout(self, post, language):
        layout = Template(
            '{% load post_content %}'
            '{{ post|post_main_caption|render_post_content }}'
            '<div id="test-media">MEDIA</div>'
            '{% include "auctions/includes/'
            '_post_marketing_suffix.html" %}'
            '{% include "auctions/includes/'
            '_post_hashtags.html" %}'
        )

        return layout.render(Context({
            "post": post,
            "language": language,
        }))

    def test_all_localized_versions(self):
        for token in ("name", "biz"):
            for language in ("en", "es", "pt"):
                with self.subTest(
                    token=token, language=language
                ):
                    post = self.prepare(token, language)
                    result = post.legacy_marketing_presentation

                    self.assertIsNotNone(result)
                    self.assertEqual(
                        result.promotional_token, token
                    )

                    self.assertEqual(
                        post_main_caption(post),
                        self.caption,
                    )

                    self.assertEqual(
                        result.caption + "\n\n" + result.suffix,
                        post_body(post.display_content),
                    )

                    html = str(render_post_marketing(post))

                    self.assertIn(f"@{token}", html)
                    self.assertNotIn(
                        f'/auctions/mention/{token}/',
                        html,
                    )
                    self.assertIn(
                        f'href="{self.destination}"',
                        html,
                    )

                    if language == "es":
                        self.assertIn("RedirectTo:", html)
                        self.assertIn("Cariñosamente, 😕", html)
                        self.assertIn(
                            '/auctions/mention/Mia/',
                            html,
                        )
                        self.assertNotIn("XOXO 💕", html)

                    if language == "pt":
                        self.assertEqual(
                            html.count("XOXO 💕"), 1
                        )

    def test_shared_template_layout(self):
        post = self.prepare()
        html = self.render_layout(post, "en")

        self.assertEqual(
            html.count('class="post-marketing-suffix"'),
            1,
        )

        self.assertEqual(
            html.count('href="/auctions/mention/name/"'),
            1,
        )

        self.assertIn(
            'href="/auctions/mention/Mia/"',
            html,
        )

        self.assertLess(
            html.index('id="test-media"'),
            html.index('class="post-marketing-suffix"'),
        )

        self.assertLess(
            html.index('class="post-marketing-suffix"'),
            html.index('class="post-tags"'),
        )

    def test_paid_post_rejected(self):
        FeedPost.objects.filter(
            pk=self.posts["name"]
        ).update(is_paid=True)

        post = self.prepare()

        self.assertIsNone(
            post.legacy_marketing_presentation
        )
        self.assertEqual(post_marketing_suffix(post), "")

    def test_private_post_rejected(self):
        FeedPost.objects.filter(
            pk=self.posts["name"]
        ).update(is_public=False)

        post = self.prepare()

        self.assertIsNone(
            post.legacy_marketing_presentation
        )
        self.assertEqual(post_marketing_suffix(post), "")

    def test_missing_publication_rejected(self):
        ScheduledPublication.objects.filter(
            feed_post_id=self.posts["name"]
        ).delete()

        post = self.prepare()

        self.assertIsNone(
            post.legacy_marketing_presentation
        )
        self.assertEqual(post_marketing_suffix(post), "")

    def test_non_platform_owner_rejected(self):
        post = FeedPost.objects.get(
            pk=self.posts["name"]
        )

        UserProfile.objects.filter(
            user_id=post.user_id
        ).update(is_platform_account=False)

        prepared = self.prepare()

        self.assertIsNone(
            prepared.legacy_marketing_presentation
        )

    def test_changed_snapshot_rejected(self):
        ScheduledPublication.objects.filter(
            feed_post_id=self.posts["name"]
        ).update(content="Changed snapshot")

        post = self.prepare()

        self.assertIsNone(
            post.legacy_marketing_presentation
        )

    def test_malformed_translation_fallback(self):
        row = FeedPostTranslation.objects.get(
            post_id=self.posts["biz"],
            language="pt",
        )

        malformed = (
            row.content
            + "\n\n---\n\nAI commentary."
        )

        FeedPostTranslation.objects.filter(
            pk=row.pk
        ).update(content=malformed)

        post = self.prepare("biz", "pt")

        self.assertIsNone(
            post.legacy_marketing_presentation
        )

        self.assertEqual(
            post_main_caption(post),
            post_body(malformed),
        )

        self.assertEqual(
            post_marketing_suffix(post), ""
        )

    def test_no_language_fallback(self):
        post = self.prepare(language=None)

        self.assertEqual(
            post.display_content,
            post.content,
        )

        self.assertIsNotNone(
            post.legacy_marketing_presentation
        )

    def test_preparation_does_not_write_storage(self):
        pk = self.posts["name"]

        before = FeedPost.objects.values(
            "content", "title"
        ).get(pk=pk)

        translations_before = list(
            FeedPostTranslation.objects.filter(
                post_id=pk
            ).order_by("language").values()
        )

        for language in ("en", "es", "pt"):
            post = self.prepare("name", language)
            self.render_layout(post, language)

        self.assertEqual(
            FeedPost.objects.values(
                "content", "title"
            ).get(pk=pk),
            before,
        )

        self.assertEqual(
            list(
                FeedPostTranslation.objects.filter(
                    post_id=pk
                ).order_by("language").values()
            ),
            translations_before,
        )

    def test_preparation_query_count_is_constant(self):
        for ids in (
            [self.posts["name"]],
            list(self.posts.values()),
        ):
            with self.subTest(posts=len(ids)):
                with self.assertNumQueries(3):
                    prepared = prepare_feed_posts(
                        FeedPost.objects.filter(pk__in=ids),
                        language="es",
                    )

                self.assertEqual(
                    len(prepared), len(ids)
                )

                with self.assertNumQueries(0):
                    for post in prepared:
                        self.assertIsNotNone(
                            post.legacy_marketing_presentation
                        )
                        post_main_caption(post)
                        post_marketing_suffix(post)
                        render_post_marketing(post)

    def test_canonical_preparation_uses_one_query(self):
        with self.assertNumQueries(1):
            prepared = prepare_feed_posts(
                FeedPost.objects.filter(
                    pk__in=self.posts.values()
                ),
                language=None,
            )

        with self.assertNumQueries(0):
            for post in prepared:
                self.assertIsNotNone(
                    post.legacy_marketing_presentation
                )
                render_post_marketing(post)

    def test_materialized_list_without_language(self):
        posts = list(
            FeedPost.objects.filter(
                pk__in=self.posts.values()
            )
        )

        with self.assertNumQueries(3):
            prepared = prepare_feed_posts(posts)

        self.assertEqual(len(prepared), 2)

        with self.assertNumQueries(0):
            for post in prepared:
                self.assertIsNotNone(
                    post.legacy_marketing_presentation
                )
                render_post_marketing(post)

    def test_materialized_list_with_language(self):
        posts = list(
            FeedPost.objects.filter(
                pk__in=self.posts.values()
            )
        )

        with self.assertNumQueries(5):
            prepared = prepare_feed_posts(
                posts, language="es"
            )

        self.assertEqual(len(prepared), 2)

        with self.assertNumQueries(0):
            for post in prepared:
                self.assertIsNotNone(
                    post.legacy_marketing_presentation
                )
                self.assertIn(
                    "RedirectTo:",
                    str(render_post_marketing(post)),
                )

    def test_empty_materialized_collection(self):
        with self.assertNumQueries(0):
            self.assertEqual(
                prepare_feed_posts([]), []
            )
            self.assertEqual(
                prepare_feed_posts([], language="pt"), []
            )

    def test_materialized_iterator(self):
        posts = list(
            FeedPost.objects.filter(
                pk__in=self.posts.values()
            )
        )

        with self.assertNumQueries(3):
            prepared = prepare_feed_posts(iter(posts))

        self.assertEqual(len(prepared), 2)

        with self.assertNumQueries(0):
            for post in prepared:
                self.assertIsNotNone(
                    post.legacy_marketing_presentation
                )
                render_post_marketing(post)
