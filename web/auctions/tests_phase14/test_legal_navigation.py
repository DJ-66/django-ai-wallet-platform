"""Legal links on login, profile editing, and business listing."""

from django.template.loader import get_template
from django.test import SimpleTestCase


class LegalNavigationTests(SimpleTestCase):
    TEMPLATES = (
        "account/login.html",
        "auctions/edit_profile.html",
        "businesses/business_form.html",
    )

    def test_legal_destinations_present(self):
        for template_name in self.TEMPLATES:
            with self.subTest(template=template_name):
                source = get_template(template_name).template.source

                self.assertIn(
                    'href="https://fanz.to/tos/"',
                    source,
                )
                self.assertIn(
                    'href="https://fanz.to/PrivacyPolicy/"',
                    source,
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
