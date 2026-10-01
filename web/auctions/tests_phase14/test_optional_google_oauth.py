from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse


class OptionalGoogleOAuthTests(TestCase):
    def setUp(self):
        self.site = Site.objects.get_current()

    def _configure_google(self):
        app = SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="test-google-client-id",
            secret="test-google-client-secret",
        )
        app.sites.add(self.site)
        return app

    def test_auth_pages_render_without_google_social_app(self):
        self.assertFalse(
            SocialApp.objects.filter(
                provider="google",
                sites=self.site,
            ).exists()
        )

        for url_name in ("account_login", "account_signup"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertNotContains(
                    response,
                    "/accounts/google/login/",
                )

    def test_auth_pages_show_google_when_configured(self):
        self._configure_google()

        for url_name in ("account_login", "account_signup"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    "/accounts/google/login/",
                )
