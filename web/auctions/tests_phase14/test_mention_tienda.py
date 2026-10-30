from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from auctions.models import FounderAccount


class MentionTiendaRoutingTests(TestCase):

    def mention(self, username):
        return reverse(
            "resolve_mention",
            kwargs={"username": username},
        )

    def test_existing_active_user_keeps_profile(self):
        User.objects.create_user(
            username="ActiveCreator",
            password="test-password",
        )

        response = self.client.get(
            self.mention("ActiveCreator")
        )

        self.assertRedirects(
            response,
            "/ActiveCreator/",
            fetch_redirect_response=False,
        )

    def test_existing_inactive_user_keeps_profile(self):
        User.objects.create_user(
            username="abc",
            password="test-password",
            is_active=False,
        )

        response = self.client.get(
            self.mention("abc")
        )

        self.assertRedirects(
            response,
            "/abc/",
            fetch_redirect_response=False,
        )

    def test_missing_eligible_handle_prefills_tienda(self):
        response = self.client.get(
            self.mention("abcd")
        )

        self.assertRedirects(
            response,
            "/auctions/founder/tienda/"
            "?handle=abcd&budget=300#founder-vending",
            fetch_redirect_response=False,
        )

    def test_missing_long_username_keeps_profile_route(self):
        response = self.client.get(
            self.mention("longusername")
        )

        self.assertRedirects(
            response,
            "/longusername/",
            fetch_redirect_response=False,
        )

    def test_owned_founder_is_not_advertised(self):
        owner = User.objects.create_user(
            username="FounderOwner",
            password="test-password",
        )

        FounderAccount.objects.create(
            handle="abcd",
            owner_root=owner,
            status=FounderAccount.STATUS_OWNED,
        )

        response = self.client.get(
            self.mention("abcd")
        )

        self.assertRedirects(
            response,
            "/abcd/",
            fetch_redirect_response=False,
        )

    def test_reserved_founder_is_not_advertised(self):
        FounderAccount.objects.create(
            handle="abcd",
            status=FounderAccount.STATUS_RESERVED,
        )

        response = self.client.get(
            self.mention("abcd")
        )

        self.assertRedirects(
            response,
            "/abcd/",
            fetch_redirect_response=False,
        )


class MentionTiendaPrefillTests(TestCase):

    def setUp(self):
        from auctions.models import BidWallet

        self.user = User.objects.create_user(
            username="TiendaVisitor",
            password="test-password",
        )

        self.wallet = BidWallet.objects.create(
            user=self.user,
            credits=500,
        )

    def test_authenticated_prefill_without_reservation(self):
        from auctions.models import (
            FounderCartItem,
            FounderVendingHold,
        )

        self.client.force_login(self.user)

        url = reverse("founder_tienda")
        response = self.client.get(
            url,
            {
                "handle": "abcd",
                "budget": "300",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'value="abcd"',
        )

        self.assertContains(
            response,
            'value="300"',
        )

        self.assertEqual(
            FounderCartItem.objects.count(),
            0,
        )

        self.assertEqual(
            FounderVendingHold.objects.count(),
            0,
        )

        self.wallet.refresh_from_db()

        self.assertEqual(
            self.wallet.credits,
            500,
        )

    def test_anonymous_prefill_redirects_to_login(self):
        response = self.client.get(
            reverse("founder_tienda"),
            {
                "handle": "abcd",
                "budget": "300",
            },
        )

        self.assertEqual(response.status_code, 302)

        location = response["Location"]

        self.assertIn("next=", location)
        self.assertIn("handle%3Dabcd", location)
        self.assertIn("budget%3D300", location)
