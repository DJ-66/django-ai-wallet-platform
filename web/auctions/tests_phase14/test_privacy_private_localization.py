from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from auctions.models import FeedPost


class PrivatePrivacyLocalizationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.policy_user = User.objects.create_user(username="PrivacyPolicy")
        self.other_user = User.objects.create_user(username="private_other")

        self.policy = FeedPost.objects.create(
            user=self.policy_user,
            title="Privacy Policy",
            content="Legal content for localization.",
            is_public=False,
        )
        self.other = FeedPost.objects.create(
            user=self.other_user,
            title="Private notes",
            content="Do not localize.",
            is_public=False,
        )

    def test_private_flag_requires_post_id(self):
        with self.assertRaises(CommandError):
            call_command("localize_feed_posts", include_private=True)

    def test_private_flag_rejects_status(self):
        with self.assertRaises(CommandError):
            call_command(
                "localize_feed_posts",
                include_private=True,
                post_id=self.policy.pk,
                status=True,
            )

    def test_other_private_account_rejected(self):
        with self.assertRaises(CommandError):
            call_command(
                "localize_feed_posts",
                include_private=True,
                post_id=self.other.pk,
                dry_run=True,
            )

    def test_private_policy_not_selected_without_flag(self):
        with patch(
            "auctions.management.commands.localize_feed_posts.localize_feed_post"
        ) as localize:
            call_command(
                "localize_feed_posts",
                post_id=self.policy.pk,
                dry_run=True,
                stdout=StringIO(),
            )
        localize.assert_not_called()

    def test_explicit_policy_post_is_selected(self):
        with patch(
            "auctions.management.commands.localize_feed_posts.localize_feed_post"
        ) as localize:
            localize.return_value = {
                "status": "complete",
                "created": 0,
            }
            call_command(
                "localize_feed_posts",
                post_id=self.policy.pk,
                dry_run=True,
                stdout=StringIO(),
            )
            localize.assert_not_called()

            call_command(
                "localize_feed_posts",
                post_id=self.policy.pk,
                include_private=True,
                dry_run=True,
                stdout=StringIO(),
            )
            localize.assert_called_once()
            self.assertEqual(localize.call_args.args[0].pk, self.policy.pk)

        self.policy.refresh_from_db()
        self.assertFalse(self.policy.is_public)
