from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import PlatformAccountForm, SignUpForm


class FounderNamespaceSignupTests(TestCase):
    def test_public_signup_rejects_one_to_four_character_names(self):
        for username in ("x", "xo", "lya", "ratt"):
            with self.subTest(username=username):
                form = SignUpForm(
                    data={
                        "username": username,
                        "email": f"{username}@example.test",
                        "password": "test-password-123",
                        "password_confirm": "test-password-123",
                    }
                )

                self.assertFalse(form.is_valid())
                self.assertIn("username", form.errors)
                self.assertTrue(
                    form.errors.get("username"),
                    form.errors.as_json(),
                )

    def test_public_signup_accepts_five_character_name(self):
        form = SignUpForm(
            data={
                "username": "ratt5",
                "email": "ratt5@example.test",
                "password": "test-password-123",
                "password_confirm": "test-password-123",
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

    def test_platform_account_form_can_use_short_name(self):
        form = PlatformAccountForm(
            data={
                "username": "lya",
                "display_name": "Lya",
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

    def test_allauth_signup_route_redirects_to_fanz_signup(self):
        response = self.client.get(
            "/accounts/signup/",
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("signup"),
        )

    def test_canonical_signup_route_uses_fanz_form(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(
            response.context["form"],
            SignUpForm,
        )

    def test_rejected_short_signup_does_not_create_user(self):
        User = get_user_model()

        response = self.client.post(
            reverse("signup"),
            {
                "username": "ratt",
                "email": "ratt@example.test",
                "password": "test-password-123",
                "password_confirm": "test-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            User.objects.filter(
                username__iexact="ratt"
            ).exists()
        )
