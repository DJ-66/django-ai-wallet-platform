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


class FeedPostLocalizedImageTests(TestCase):
    """Localized image selection without modifying original media."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from auctions.models import FeedPost, FeedPostTranslation

        User = get_user_model()

        self.user = User.objects.create_user(
            username="localized_image_tester"
        )

        self.post = FeedPost.objects.create(
            user=self.user,
            title="About FANZ",
            content="Welcome to FANZ",
            is_public=True,
            is_paid=False,
            image="feed/original.webp",
        )

        for lang in ("en", "es", "pt"):
            FeedPostTranslation.objects.create(
                post=self.post,
                language=lang,
                title=f"Title {lang}",
                content=f"Content {lang}",
                image=f"feed/translations/{lang}.webp",
            )

    def prepared(self, lang):
        from auctions.services import prepare_feed_posts

        return prepare_feed_posts(
            FeedPost.objects.filter(pk=self.post.pk),
            language=lang,
        )[0]

    def test_each_language_selects_its_image(self):
        for lang in ("en", "es", "pt"):
            with self.subTest(language=lang):
                post = self.prepared(lang)

                self.assertIn(
                    f"{lang}.webp",
                    post.localized_cover_url,
                )

                self.assertEqual(
                    post.display_title,
                    f"Title {lang}",
                )

    def test_missing_translation_image_falls_back(self):
        from auctions.models import FeedPostTranslation

        translation = FeedPostTranslation.objects.get(
            post=self.post,
            language="es",
        )

        translation.image = None
        translation.save(update_fields=["image"])

        post = self.prepared("es")

        self.assertIsNone(post.localized_cover_url)

    def test_paid_post_does_not_expose_localized_image(self):
        self.post.is_paid = True
        self.post.save(update_fields=["is_paid"])

        post = self.prepared("es")

        self.assertIsNone(post.localized_cover_url)

    def test_nonpublic_post_does_not_use_localized_image(self):
        self.post.is_public = False
        self.post.save(update_fields=["is_public"])

        post = self.prepared("pt")

        self.assertIsNone(post.localized_cover_url)

    def test_multiple_media_items_preserve_original_gallery(self):
        from auctions.models import FeedPostMedia

        self.post.image = None
        self.post.save(update_fields=["image"])

        for number in (1, 2):
            FeedPostMedia.objects.create(
                post=self.post,
                file=f"feed/media/image-{number}.webp",
                media_type="image",
                is_active=True,
                display_order=number,
            )

        post = self.prepared("es")

        self.assertIsNone(post.localized_cover_url)

    def test_single_media_image_can_be_localized(self):
        from auctions.models import FeedPostMedia

        self.post.image = None
        self.post.save(update_fields=["image"])

        FeedPostMedia.objects.create(
            post=self.post,
            file="feed/media/original.webp",
            media_type="image",
            is_active=True,
        )

        post = self.prepared("pt")

        self.assertIn(
            "pt.webp",
            post.localized_cover_url,
        )


class FeedPostLocalizedImageRenderingTests(TestCase):
    """Verify localized cover and lightbox URLs in rendered HTML."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from auctions.models import (
            FeedPost,
            FeedPostMedia,
            FeedPostTranslation,
        )

        User = get_user_model()
        self.user = User.objects.create_user(
            username="localized_render_tester"
        )

        self.post = FeedPost.objects.create(
            user=self.user,
            title="About FANZ",
            content="Welcome to FANZ",
            is_public=True,
            is_paid=False,
        )

        FeedPostMedia.objects.create(
            post=self.post,
            file="feed/media/original.webp",
            media_type="image",
            is_active=True,
        )

        for lang in ("en", "es", "pt"):
            FeedPostTranslation.objects.create(
                post=self.post,
                language=lang,
                title=f"Title {lang}",
                content=f"Content {lang}",
                image=f"feed/translations/{lang}.webp",
            )

    def test_direct_post_renders_localized_cover_and_lightbox(self):
        from django.urls import reverse

        url = reverse(
            "post_detail",
            args=[self.post.pk],
        )

        for lang in ("en", "es", "pt"):
            with self.subTest(language=lang):
                response = self.client.get(
                    url,
                    {"lang": lang},
                )

                self.assertEqual(response.status_code, 200)

                expected = f"/media/feed/translations/{lang}.webp"

                self.assertContains(
                    response,
                    f'href="{expected}"',
                )
                self.assertContains(
                    response,
                    f'src="{expected}"',
                )

    def test_profile_renders_localized_cover(self):
        from django.urls import reverse

        url = reverse(
            "public_profile_root",
            kwargs={"username": self.user.username},
        )

        for lang in ("en", "es", "pt"):
            with self.subTest(language=lang):
                response = self.client.get(
                    url,
                    {"lang": lang},
                )

                self.assertEqual(response.status_code, 200)

                expected = f"/media/feed/translations/{lang}.webp"

                self.assertContains(
                    response,
                    f'href="{expected}"',
                )
                self.assertContains(
                    response,
                    f'src="{expected}"',
                )

    def test_missing_image_uses_original_cover(self):
        from django.urls import reverse
        from auctions.models import FeedPostTranslation

        translation = FeedPostTranslation.objects.get(
            post=self.post,
            language="es",
        )

        translation.image = None
        translation.save(update_fields=["image"])

        response = self.client.get(
            reverse("post_detail", args=[self.post.pk]),
            {"lang": "es"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'src="/media/feed/media/original.webp"',
        )
        self.assertNotContains(
            response,
            "/media/feed/translations/es.webp",
        )


class FeedPostLocalizedImageUploadTests(TestCase):
    """Exercise localized image uploads through the translation view."""

    def setUp(self):
        import tempfile

        from django.contrib.auth import get_user_model
        from django.test import override_settings
        from django.urls import reverse
        from auctions.models import (
            FeedPost,
            FeedPostTranslation,
        )

        self.temp_media = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)

        media_override = override_settings(
            MEDIA_ROOT=self.temp_media.name
        )
        media_override.enable()
        self.addCleanup(media_override.disable)

        User = get_user_model()

        self.user = User.objects.create_user(
            username="localized_upload_tester",
            password="test-password",
        )

        self.post = FeedPost.objects.create(
            user=self.user,
            title="About FANZ",
            content="Original content",
            image="feed/original.webp",
            is_public=True,
            is_paid=False,
        )

        self.translation = FeedPostTranslation.objects.create(
            post=self.post,
            language="es",
            title="Acerca de FANZ",
            content="Contenido en español",
        )

        self.url = reverse(
            "translate_post",
            args=[self.post.pk],
        ) + "?lang=es"

        self.client.force_login(self.user)

    def make_image(self, color="blue"):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        buffer = BytesIO()

        Image.new(
            "RGB",
            (120, 120),
            color,
        ).save(buffer, format="PNG")

        return SimpleUploadedFile(
            "localized.png",
            buffer.getvalue(),
            content_type="image/png",
        )

    def test_upload_localized_image(self):
        response = self.client.post(
            self.url,
            {
                "title": "Acerca de FANZ",
                "content": "Contenido en español",
                "image": self.make_image(),
            },
        )

        self.assertEqual(response.status_code, 302)

        self.translation.refresh_from_db()

        self.assertTrue(self.translation.image)
        self.assertTrue(
            self.translation.image.name.startswith(
                "feed/translations/"
            )
        )

        self.assertEqual(
            self.translation.content,
            "Contenido en español",
        )

    def test_replace_localized_image(self):
        self.client.post(
            self.url,
            {
                "title": "Acerca de FANZ",
                "content": "Contenido en español",
                "image": self.make_image("blue"),
            },
        )

        self.translation.refresh_from_db()
        original_name = self.translation.image.name

        response = self.client.post(
            self.url,
            {
                "title": "Acerca de FANZ",
                "content": "Contenido en español",
                "image": self.make_image("red"),
            },
        )

        self.assertEqual(response.status_code, 302)

        self.translation.refresh_from_db()

        self.assertNotEqual(
            self.translation.image.name,
            original_name,
        )

    def test_invalid_image_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.client.post(
            self.url,
            {
                "title": "Acerca de FANZ",
                "content": "Contenido en español",
                "image": SimpleUploadedFile(
                    "invalid.png",
                    b"not-an-image",
                    content_type="image/png",
                ),
            },
        )

        self.assertEqual(response.status_code, 200)

        self.translation.refresh_from_db()

        self.assertFalse(self.translation.image)

    def test_text_only_update_preserves_image(self):
        self.client.post(
            self.url,
            {
                "title": "Acerca de FANZ",
                "content": "Contenido en español",
                "image": self.make_image(),
            },
        )

        self.translation.refresh_from_db()
        image_name = self.translation.image.name

        response = self.client.post(
            self.url,
            {
                "title": "Nuevo título",
                "content": "Texto actualizado",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.translation.refresh_from_db()

        self.assertEqual(
            self.translation.image.name,
            image_name,
        )

        self.assertEqual(
            self.translation.content,
            "Texto actualizado",
        )


class FeedPostLocalizedDiscoveryTests(TestCase):
    """Localized covers must preserve Community and hashtag behavior."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from auctions.models import (
            FeedPost,
            FeedPostMedia,
            FeedPostTranslation,
            Hashtag,
        )

        User = get_user_model()

        self.user = User.objects.create_user(
            username="localized_discovery_tester"
        )

        self.tag = Hashtag.objects.create(
            name="localizedcovercheck"
        )

        self.post = FeedPost.objects.create(
            user=self.user,
            title="About FANZ",
            content="Welcome to FANZ",
            is_public=True,
            is_paid=False,
        )

        self.post.hashtags.add(self.tag)

        FeedPostMedia.objects.create(
            post=self.post,
            file="feed/media/original.webp",
            media_type="image",
            is_active=True,
        )

        for lang in ("en", "es", "pt"):
            FeedPostTranslation.objects.create(
                post=self.post,
                language=lang,
                title=f"Title {lang}",
                content=f"Content {lang}",
                image=f"feed/translations/{lang}.webp",
            )

    def test_community_feed_localized_images(self):
        from django.urls import reverse

        url = reverse("feed_home")

        for lang in ("en", "es", "pt"):
            with self.subTest(language=lang):
                response = self.client.get(
                    url,
                    {"lang": lang},
                )

                self.assertEqual(response.status_code, 200)

                self.assertContains(
                    response,
                    f"/media/feed/translations/{lang}.webp",
                )

    def test_hashtag_feed_localized_images(self):
        from django.urls import reverse

        url = reverse(
            "hashtag_feed",
            args=[self.tag.name],
        )

        for lang in ("en", "es", "pt"):
            with self.subTest(language=lang):
                response = self.client.get(
                    url,
                    {"lang": lang},
                )

                self.assertEqual(response.status_code, 200)

                self.assertContains(
                    response,
                    f"/media/feed/translations/{lang}.webp",
                )

    def test_hashtag_discovery_remains_based_on_original_media(self):
        from auctions.services import (
            get_public_hashtag_posts,
            get_public_hashtag_post_count,
        )

        post_ids = list(
            get_public_hashtag_posts(self.tag)
            .values_list("id", flat=True)
        )

        self.assertIn(self.post.pk, post_ids)

        self.assertEqual(
            get_public_hashtag_post_count(self.tag),
            1,
        )

    def test_paid_post_does_not_enter_public_discovery(self):
        from auctions.services import get_public_hashtag_posts

        self.post.is_paid = True
        self.post.save(update_fields=["is_paid"])

        self.assertFalse(
            get_public_hashtag_posts(self.tag)
            .filter(pk=self.post.pk)
            .exists()
        )

    def test_old_post_remains_on_hashtag_but_not_community(self):
        from datetime import timedelta
        from django.utils import timezone
        from django.urls import reverse
        from auctions.services import get_public_hashtag_posts

        FeedPost = type(self.post)

        FeedPost.objects.filter(
            pk=self.post.pk
        ).update(
            created_at=timezone.now() - timedelta(days=5)
        )

        community = self.client.get(
            reverse("feed_home"),
            {"lang": "es"},
        )

        self.assertEqual(community.status_code, 200)

        self.assertNotContains(
            community,
            "Content es",
        )

        self.assertTrue(
            get_public_hashtag_posts(self.tag)
            .filter(pk=self.post.pk)
            .exists()
        )
