"""Legal links on login, profile editing, and business listing."""

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.template import Context
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from django.utils import translation


class LegalNavigationTests(SimpleTestCase):
    class BusinessAcceptanceForm(forms.Form):
        tos_accepted = forms.BooleanField(required=False)

    FEED_TEMPLATE = "auctions/feed_home.html"
    REQUEST_LANGUAGE_TEMPLATES = (
        "account/login.html",
        "auctions/edit_profile.html",
        "businesses/business_form.html",
    )

    def setUp(self):
        self.request_factory = RequestFactory()

    def render_template(
        self,
        template_name,
        request_language=None,
        active_language="en",
        context_language=None,
    ):
        query = (
            {}
            if request_language is None
            else {"lang": request_language}
        )
        request = self.request_factory.get("/", query)
        request.user = AnonymousUser()
        request.LANGUAGE_CODE = active_language

        context = {"request": request}
        if context_language is not None:
            context["language"] = context_language
        if template_name == "businesses/business_form.html":
            context["form"] = self.BusinessAcceptanceForm()

        with translation.override(active_language):
            return get_template(template_name).template.render(
                Context(context)
            )

    def test_terms_destinations_preserved(self):
        for template_name in self.REQUEST_LANGUAGE_TEMPLATES:
            with self.subTest(template=template_name):
                source = get_template(template_name).template.source

                self.assertIn(
                    'href="https://fanz.to/tos/"',
                    source,
                )

    def test_feed_privacy_link_uses_language_context(self):
        for language in ("en", "es", "pt"):
            with self.subTest(language=language):
                rendered = self.render_template(
                    self.FEED_TEMPLATE,
                    request_language="invalid",
                    context_language=language,
                )

                self.assertIn(
                    "https://fanz.to/PrivacyPolicy/"
                    f"?lang={language}",
                    rendered,
                )

    def test_request_privacy_links_preserve_supported_languages(self):
        for template_name in self.REQUEST_LANGUAGE_TEMPLATES:
            for language in ("en", "es", "pt"):
                with self.subTest(
                    template=template_name,
                    language=language,
                ):
                    rendered = self.render_template(
                        template_name,
                        request_language=language,
                    )

                    self.assertIn(
                        "https://fanz.to/PrivacyPolicy/"
                        f"?lang={language}",
                        rendered,
                    )

    def test_request_language_wins_over_active_language(self):
        for template_name in self.REQUEST_LANGUAGE_TEMPLATES:
            with self.subTest(template=template_name):
                rendered = self.render_template(
                    template_name,
                    request_language="pt",
                    active_language="es",
                )

                self.assertIn(
                    "https://fanz.to/PrivacyPolicy/?lang=pt",
                    rendered,
                )

    def test_missing_request_language_uses_active_language(self):
        for template_name in self.REQUEST_LANGUAGE_TEMPLATES:
            for active_language in ("en", "es", "pt"):
                with self.subTest(
                    template=template_name,
                    active_language=active_language,
                ):
                    rendered = self.render_template(
                        template_name,
                        active_language=active_language,
                    )

                    self.assertIn(
                        "https://fanz.to/PrivacyPolicy/"
                        f"?lang={active_language}",
                        rendered,
                    )

    def test_invalid_request_language_uses_active_language(self):
        for template_name in self.REQUEST_LANGUAGE_TEMPLATES:
            with self.subTest(template=template_name):
                rendered = self.render_template(
                    template_name,
                    request_language="invalid",
                    active_language="es",
                )

                self.assertIn(
                    "https://fanz.to/PrivacyPolicy/?lang=es",
                    rendered,
                )

    def test_invalid_language_falls_back_to_english(self):
        templates = (
            (self.FEED_TEMPLATE, {"context_language": "invalid"}),
            *((template_name, {}) for template_name in (
                self.REQUEST_LANGUAGE_TEMPLATES
            )),
        )

        for template_name, options in templates:
            with self.subTest(template=template_name):
                rendered = self.render_template(
                    template_name,
                    request_language="invalid",
                    active_language="fr",
                    **options,
                )

                self.assertIn(
                    "https://fanz.to/PrivacyPolicy/?lang=en",
                    rendered,
                )
                self.assertNotIn(
                    "https://fanz.to/PrivacyPolicy/?lang=invalid",
                    rendered,
                )

    def test_login_has_no_new_acceptance_checkbox(self):
        source = get_template(
            "account/login.html"
        ).template.source
        self.assertNotIn('name="tos_accepted"', source)

    def test_profile_acceptance_field_preserved(self):
        source = get_template(
            "auctions/edit_profile.html"
        ).template.source
        self.assertIn('name="tos_accepted"', source)

    def test_business_acceptance_field_preserved(self):
        source = get_template(
            "businesses/business_form.html"
        ).template.source
        self.assertIn('field.name == "tos_accepted"', source)
