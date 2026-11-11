from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from auctions.views import feed_home


class AllTagsLocalizationTests(SimpleTestCase):
    PROMOTION_COPY = {
        "en": (
            "Promote Everywhere (20 CR)",
            (
                "Permanent syndication to all hashtag feeds, Max 1 per "
                "24hrs, Free image posts only."
            ),
            (
                "Promote this post permanently across eligible FANZ "
                "hashtag feeds for 20 FANZ Credits? Maximum one promotion "
                "every 24 hours."
            ),
        ),
        "es": (
            "Promocionar en todas partes (20 CR)",
            (
                "Distribución permanente en todos los feeds de hashtags, "
                "máximo 1 cada 24 h, solo publicaciones gratuitas con "
                "imágenes."
            ),
            (
                "¿Promocionar esta publicación permanentemente en los feeds "
                "de hashtags elegibles de FANZ por 20 créditos FANZ? Máximo "
                "una promoción cada 24 horas."
            ),
        ),
        "pt": (
            "Promover em todos os lugares (20 CR)",
            (
                "Distribuição permanente em todos os feeds de hashtags, no "
                "máximo 1 a cada 24 h, somente publicações gratuitas com "
                "imagens."
            ),
            (
                "Promover esta publicação permanentemente nos feeds de "
                "hashtags qualificados da FANZ por 20 créditos FANZ? No "
                "máximo uma promoção a cada 24 horas."
            ),
        ),
    }

    @staticmethod
    def render_without_context_processors(
        request,
        template_name,
        context,
    ):
        return HttpResponse(render_to_string(template_name, context))

    def setUp(self):
        self.request_factory = RequestFactory()

    def render_feed(self, language):
        request = self.request_factory.get(
            reverse("feed_home"),
            {"lang": language},
        )
        request.user = AnonymousUser()
        request.LANGUAGE_CODE = "en"

        with (
            patch(
                "auctions.views.prepare_feed_posts",
                return_value=[],
            ),
            patch("auctions.views.FeedPost.objects.filter"),
            patch(
                "auctions.views.BusinessUpdate.objects.select_related"
            ) as business_updates,
            patch("auctions.views.Event.objects.select_related") as events,
            patch(
                "auctions.views.render",
                side_effect=self.render_without_context_processors,
            ),
        ):
            business_updates.return_value.filter.return_value = []
            events.return_value.filter.return_value = []
            return feed_home(request)

    def test_alltags_promotion_uses_requested_language(self):
        for language, expected_copy in self.PROMOTION_COPY.items():
            with self.subTest(language=language):
                response = self.render_feed(language)

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "#allTags")
                self.assertContains(response, "20 CR")

                for text in expected_copy:
                    self.assertContains(response, text)
