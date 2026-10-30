"""Cross-path FANZ registration concurrency regression."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import Client, TransactionTestCase
from django.urls import reverse

from auctions.forms import SignUpForm
from auctions.models import BidWallet
from businesses.forms_onboarding import GuestBusinessAccountForm
from businesses.models import BusinessListing


User = get_user_model()


class CrossPathRegistrationTests(TransactionTestCase):

    def test_business_and_signup_same_email_create_one_account(self):
        self.assertEqual(connection.vendor, "postgresql")

        barrier = Barrier(2, timeout=15)
        shared_email = "cross-path-race@example.com"

        original_is_valid = SignUpForm.is_valid

        def synchronized_validation(form):
            valid = original_is_valid(form)

            if valid:
                barrier.wait()

            return valid

        def register_business():
            close_old_connections()
            try:
                client = Client(raise_request_exception=False)

                return client.post(
                    reverse("businesses:create"),
                    {
                        "name": "Cross Path Business",
                        "industry": "services",
                        "city": "Encarnacion",
                        "country": "Paraguay",
                        "email": "contact@crosspath.example",
                        "tos_accepted": "on",
                        "account-username": "crosspathbusiness",
                        "account-email": shared_email,
                        "account-password": "SecureBusinessPass2026!",
                        "account-password_confirm":
                            "SecureBusinessPass2026!",
                    },
                )
            finally:
                close_old_connections()

        def register_signup():
            close_old_connections()
            try:
                client = Client(raise_request_exception=False)

                return client.post(
                    reverse("signup"),
                    {
                        "username": "crosspathsignup",
                        "email": shared_email.upper(),
                        "password": "SecureSignupPass2026!",
                        "password_confirm": "SecureSignupPass2026!",
                    },
                )
            finally:
                close_old_connections()

        with (
            patch.object(
                SignUpForm,
                "is_valid",
                synchronized_validation,
            ),
            patch(
                "auctions.views.send_activation_email"
            ) as activation_email,
            patch(
                "auctions.wallet_setup.send_welcome_email"
            ),
            patch(
                "auctions.wallet_setup._generate_wallet_qr_codes"
            ),
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                business_future = executor.submit(
                    register_business
                )
                signup_future = executor.submit(
                    register_signup
                )

                business_response = business_future.result(
                    timeout=30
                )
                signup_response = signup_future.result(
                    timeout=30
                )

        statuses = [
            business_response.status_code,
            signup_response.status_code,
        ]

        self.assertEqual(signup_response.status_code, 200)
        self.assertIn(business_response.status_code, (200, 302))

        users = User.objects.filter(
            email__iexact=shared_email
        )

        self.assertEqual(users.count(), 1)

        self.assertEqual(
            BidWallet.objects.filter(
                user__in=users
            ).count(),
            1,
        )

        winner = users.get()

        business_count = BusinessListing.objects.filter(
            owner=winner
        ).count()

        bonus_count = BidWallet.objects.filter(
            user=winner,
            signup_bonus_given=True,
        ).count()

        if winner.username == "crosspathbusiness":
            self.assertEqual(business_response.status_code, 302)
            self.assertEqual(business_count, 1)
            self.assertTrue(winner.is_active)
            self.assertEqual(bonus_count, 1)
            activation_email.assert_not_called()

            self.assertContains(
                signup_response,
                "An account with this email already exists.",
            )

        elif winner.username == "crosspathsignup":
            self.assertEqual(business_response.status_code, 200)
            self.assertEqual(business_count, 0)
            self.assertFalse(winner.is_active)
            self.assertEqual(bonus_count, 0)
            activation_email.assert_called_once()

            self.assertContains(
                business_response,
                "An account with this email already exists.",
            )

        else:
            self.fail(
                f"Unexpected registration winner: {winner.username}"
            )

        print("Cross-path response statuses:", statuses)
        print("Cross-path winner:", winner.username)

    def test_ordinary_signup_wins_then_business_rejected(self):
        from unittest.mock import patch

        shared_email = "ordinary-wins@example.com"

        signup_data = {
            "username": "ordinarywinner",
            "email": shared_email,
            "password": "SecureSignupPass2026!",
            "password_confirm": "SecureSignupPass2026!",
        }

        business_data = {
            "name": "Ordinary Winner Business",
            "industry": "services",
            "city": "Encarnacion",
            "country": "Paraguay",
            "email": "contact@ordinarywinner.example",
            "tos_accepted": "on",
            "account-username": "businessloser",
            "account-email": shared_email.upper(),
            "account-password": "SecureBusinessPass2026!",
            "account-password_confirm": "SecureBusinessPass2026!",
        }

        with patch(
            "auctions.views.send_activation_email"
        ) as activation_email:
            signup_response = self.client.post(
                reverse("signup"),
                signup_data,
            )

        self.assertEqual(signup_response.status_code, 200)

        user = User.objects.get(
            email__iexact=shared_email
        )

        self.assertEqual(user.username, "ordinarywinner")
        self.assertFalse(user.is_active)

        activation_email.assert_called_once()

        business_response = self.client.post(
            reverse("businesses:create"),
            business_data,
        )

        self.assertEqual(business_response.status_code, 200)

        account_form = business_response.context["account_form"]

        self.assertIsNotNone(account_form)
        self.assertIn(
            "email",
            account_form.errors,
        )
        self.assertTrue(
            account_form.errors["email"],
        )

        self.assertEqual(
            User.objects.filter(
                email__iexact=shared_email
            ).count(),
            1,
        )

        self.assertEqual(
            BidWallet.objects.filter(
                user=user
            ).count(),
            1,
        )

        self.assertEqual(
            BusinessListing.objects.filter(
                owner=user
            ).count(),
            0,
        )

        self.assertEqual(
            BidWallet.objects.filter(
                user=user,
                signup_bonus_given=True,
            ).count(),
            0,
        )

        print("PASS: Ordinary signup winner preserved")
        print("PASS: Duplicate business signup rejected")
