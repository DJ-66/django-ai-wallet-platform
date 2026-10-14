"""Owner-only navigation controls on FANZ public profiles."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ProfileOwnerNavigationTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="profile_nav_owner",
        )
        self.visitor = User.objects.create_user(
            username="profile_nav_visitor",
        )

        self.url = reverse(
            "public_profile_root",
            kwargs={"username": self.owner.username},
        )

    def assert_owner_links(self, response, visible):
        for destination in (
            "/auctions/platform/accounts/",
            "/b/my/businesses/",
        ):
            if visible:
                self.assertContains(response, f'href="{destination}"')
            else:
                self.assertNotContains(response, f'href="{destination}"')

    def test_owner_sees_both_management_links(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assert_owner_links(response, visible=True)
        self.assertContains(
            response,
            'href="/auctions/profile/edit/"',
        )

    def test_other_logged_in_user_does_not_see_links(self):
        self.client.force_login(self.visitor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assert_owner_links(response, visible=False)

    def test_anonymous_visitor_does_not_see_links(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assert_owner_links(response, visible=False)
