from django.contrib.auth import get_user_model
from django.test import TestCase

from auctions.models import (
    FeedPost,
    FeedPostTranslation,
)
from auctions.post_localization import (
    PostLocalizationError,
    _mask_protected_tokens,
    _restore_protected_tokens,
    _validate_preserved_tokens,
    localize_feed_post,
)
from auctions.services import prepare_feed_posts


class QueueProvider:
    """
    Deterministic fake for the final localization architecture.

    Responses are consumed in order. This lets tests model separate
    title/content calls and safety retries without Ollama.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    def generate_reply(
        self,
        system_prompt,
        history,
        num_predict=512,
    ):
        self.calls += 1
        self.prompts.append(system_prompt)

        if not self.responses:
            raise AssertionError(
                "Unexpected provider call"
            )

        response = self.responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response


class FeedPostLocalizationTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="localizer",
            password="test",
        )

        self.post = FeedPost.objects.create(
            user=self.user,
            title="FANZ Link Test",
            content=(
                "Hello @Rick — visit "
                "[Founder Tienda]"
                "(https://fanz.to/auctions/founder/tienda/"
                "?ref=fanz&utm_source=test). "
                "#FANZ #CreatorEconomy"
            ),
            is_public=True,
        )

        FeedPostTranslation.objects.create(
            post=self.post,
            language="en",
            title=self.post.title,
            content=self.post.content,
        )

    def _safe_es_pt_provider(self):
        # The localizer masks protected tokens before sending content
        # to the provider. Token numbering is per title/content string.
        return QueueProvider([
            # ES title
            "Prueba de enlace FANZ",

            # ES content
            (
                "Hola FANZPROTECTEDTOKEN0END — visita "
                "[Founder Tienda]"
                "(FANZPROTECTEDTOKEN1END). "
                "FANZPROTECTEDTOKEN2END "
                "FANZPROTECTEDTOKEN3END"
            ),

            # PT title
            "Teste de link FANZ",

            # PT content
            (
                "Olá FANZPROTECTEDTOKEN0END — visite "
                "[Founder Tienda]"
                "(FANZPROTECTEDTOKEN1END). "
                "FANZPROTECTEDTOKEN2END "
                "FANZPROTECTEDTOKEN3END"
            ),
        ])

    def test_mask_restore_round_trip_preserves_protected_tokens(self):
        source = (
            "rick3 says hello to @Rick "
            "#FANZ "
            "https://example.com/product"
            "?id=42&ref=fanz123"
        )

        masked, tokens = _mask_protected_tokens(
            source
        )

        self.assertNotIn(
            "rick3",
            masked,
        )
        self.assertNotIn(
            "@Rick",
            masked,
        )
        self.assertNotIn(
            "#FANZ",
            masked,
        )
        self.assertNotIn(
            "https://example.com",
            masked,
        )

        self.assertEqual(
            _restore_protected_tokens(
                masked,
                tokens,
            ),
            source,
        )

    def test_validator_rejects_invented_mention(self):
        with self.assertRaises(
            PostLocalizationError
        ):
            _validate_preserved_tokens(
                "rick3 post context",
                "@rick3 contexto de publicación",
                language="es",
            )

    def test_validator_rejects_changed_affiliate_url(self):
        source = (
            "Visit https://example.com/"
            "?ref=fanz&utm_source=test #FANZ"
        )

        translated = (
            "Visita https://example.com/"
            "?ref=changed&utm_source=test #FANZ"
        )

        with self.assertRaises(
            PostLocalizationError
        ):
            _validate_preserved_tokens(
                source,
                translated,
                language="es",
            )

    def test_creates_missing_languages_and_preserves_existing_english(self):
        original = FeedPostTranslation.objects.get(
            post=self.post,
            language="en",
        )

        original.content = "MANUAL ENGLISH"
        original.save(
            update_fields=["content"]
        )

        provider = self._safe_es_pt_provider()

        result = localize_feed_post(
            self.post,
            provider=provider,
        )

        original.refresh_from_db()

        self.assertEqual(
            original.content,
            "MANUAL ENGLISH",
        )

        self.assertEqual(
            set(result["created"]),
            {"es", "pt"},
        )

        es = FeedPostTranslation.objects.get(
            post=self.post,
            language="es",
        )

        pt = FeedPostTranslation.objects.get(
            post=self.post,
            language="pt",
        )

        self.assertIn(
            "@Rick",
            es.content,
        )
        self.assertIn(
            "#FANZ",
            es.content,
        )
        self.assertIn(
            "ref=fanz&utm_source=test",
            es.content,
        )

        self.assertIn(
            "@Rick",
            pt.content,
        )

    def test_blank_translation_rows_are_repaired(self):
        for language in ("es", "pt"):
            FeedPostTranslation.objects.create(
                post=self.post,
                language=language,
                title="",
                content="",
            )

        provider = self._safe_es_pt_provider()

        result = localize_feed_post(
            self.post,
            provider=provider,
        )

        self.assertEqual(
            set(result["created"]),
            {"es", "pt"},
        )

        for language in ("es", "pt"):
            translation = (
                FeedPostTranslation.objects.get(
                    post=self.post,
                    language=language,
                )
            )

            self.assertTrue(
                translation.title.strip()
            )
            self.assertTrue(
                translation.content.strip()
            )

    def test_dry_run_writes_nothing(self):
        provider = self._safe_es_pt_provider()

        result = localize_feed_post(
            self.post,
            provider=provider,
            dry_run=True,
        )

        self.assertEqual(
            set(result["created"]),
            {"es", "pt"},
        )

        self.assertEqual(
            FeedPostTranslation.objects
            .filter(post=self.post)
            .count(),
            1,
        )

    def test_complete_post_does_not_call_provider(self):
        FeedPostTranslation.objects.create(
            post=self.post,
            language="es",
            title="Prueba FANZ",
            content="Contenido FANZ",
        )

        FeedPostTranslation.objects.create(
            post=self.post,
            language="pt",
            title="Teste FANZ",
            content="Conteúdo FANZ",
        )

        provider = QueueProvider([])

        result = localize_feed_post(
            self.post,
            provider=provider,
        )

        self.assertEqual(
            result["status"],
            "complete",
        )
        self.assertEqual(
            provider.calls,
            0,
        )

    def test_prepare_feed_posts_selects_requested_language(self):
        FeedPostTranslation.objects.create(
            post=self.post,
            language="es",
            title="Título español",
            content="Contenido español",
        )

        FeedPostTranslation.objects.create(
            post=self.post,
            language="pt",
            title="Título português",
            content="Conteúdo português",
        )

        expected = {
            "en": (
                self.post.title,
                self.post.content,
            ),
            "es": (
                "Título español",
                "Contenido español",
            ),
            "pt": (
                "Título português",
                "Conteúdo português",
            ),
        }

        for language, values in expected.items():
            prepared = prepare_feed_posts(
                FeedPost.objects.filter(
                    pk=self.post.pk
                ),
                language=language,
            )[0]

            self.assertEqual(
                prepared.display_title,
                values[0],
            )
            self.assertEqual(
                prepared.display_content,
                values[1],
            )

    def test_prepare_feed_posts_falls_back_from_blank_translation(self):
        FeedPostTranslation.objects.create(
            post=self.post,
            language="es",
            title="",
            content="",
        )

        prepared = prepare_feed_posts(
            FeedPost.objects.filter(
                pk=self.post.pk
            ),
            language="es",
        )[0]

        self.assertEqual(
            prepared.display_title,
            self.post.title,
        )
        self.assertEqual(
            prepared.display_content,
            self.post.content,
        )


    def test_repairs_non_source_row_copied_from_canonical_source(self):
        post = FeedPost.objects.create(
            user=self.user,
            title="Publicación sobre Rick 5 en español",
            content=(
                "Contexto de la publicación "
                "sobre Rick 5 en español"
            ),
            is_public=True,
        )

        # Reproduce the historical #7 state:
        # EN incorrectly contains the Spanish canonical source.
        stale_en = FeedPostTranslation.objects.create(
            post=post,
            language="en",
            title=post.title,
            content=post.content,
        )

        FeedPostTranslation.objects.create(
            post=post,
            language="es",
            title=post.title,
            content=post.content,
        )

        FeedPostTranslation.objects.create(
            post=post,
            language="pt",
            title="Postagem sobre Rick 5 em espanhol",
            content=(
                "Contexto da publicação "
                "sobre Rick 5 em espanhol"
            ),
        )

        provider = QueueProvider([
            "Post about Rick 5 in Spanish",
            (
                "Context of the post about "
                "Rick 5 in Spanish"
            ),
        ])

        result = localize_feed_post(
            post,
            provider=provider,
        )

        stale_en.refresh_from_db()

        self.assertEqual(
            result["source_language"],
            "es",
        )
        self.assertEqual(
            result["created"],
            ["en"],
        )
        self.assertEqual(
            stale_en.title,
            "Post about Rick 5 in Spanish",
        )
        self.assertEqual(
            stale_en.content,
            "Context of the post about Rick 5 in Spanish",
        )

        # Source and genuine PT localization remain untouched.
        self.assertEqual(
            FeedPostTranslation.objects.get(
                post=post,
                language="es",
            ).title,
            post.title,
        )

        self.assertEqual(
            FeedPostTranslation.objects.get(
                post=post,
                language="pt",
            ).title,
            "Postagem sobre Rick 5 em espanhol",
        )


    def test_complete_short_post_uses_matching_source_row(self):
        post = FeedPost.objects.create(
            user=self.user,
            title="test post 1 Rick",
            content="test post 1 Rick",
            is_public=True,
        )

        FeedPostTranslation.objects.create(
            post=post,
            language="en",
            title=post.title,
            content=post.content,
        )

        FeedPostTranslation.objects.create(
            post=post,
            language="es",
            title="prueba de publicación 1 Rick",
            content="prueba de publicación 1 Rick",
        )

        FeedPostTranslation.objects.create(
            post=post,
            language="pt",
            title="post de teste 1 Rick",
            content="post de teste 1 Rick",
        )

        provider = QueueProvider([])

        result = localize_feed_post(
            post,
            provider=provider,
        )

        self.assertEqual(
            result["status"],
            "complete",
        )

        self.assertEqual(
            provider.calls,
            0,
        )


class FeedPostLanguagePresentationTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="Rick",
            password="test",
        )

        self.post = FeedPost.objects.create(
            user=self.user,
            title="English title",
            content="English content",
            is_public=True,
        )

        for language, title, content in (
            (
                "en",
                "English title",
                "English content",
            ),
            (
                "es",
                "Título español",
                "Contenido español",
            ),
            (
                "pt",
                "Título português",
                "Conteúdo português",
            ),
        ):
            FeedPostTranslation.objects.create(
                post=self.post,
                language=language,
                title=title,
                content=content,
            )

    def test_post_detail_changes_with_lang_query_parameter(self):
        for language, expected in (
            ("en", "English title"),
            ("es", "Título español"),
            ("pt", "Título português"),
        ):
            response = self.client.get(
                f"/auctions/feed/post/{self.post.pk}/",
                {
                    "lang": language,
                },
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            self.assertContains(
                response,
                expected,
            )

    def test_public_profile_changes_with_lang_query_parameter(self):
        for language, expected in (
            ("en", "English title"),
            ("es", "Título español"),
            ("pt", "Título português"),
        ):
            response = self.client.get(
                f"/{self.user.username}/",
                {
                    "lang": language,
                },
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            self.assertContains(
                response,
                expected,
            )
