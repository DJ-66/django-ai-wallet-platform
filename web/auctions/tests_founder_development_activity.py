from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.founder_valuation import get_founder_valuation
from auctions.models import FeedPost, FounderAccount


class FounderDevelopmentActivityTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.dj = User.objects.create_user(
            username="DJ",
            password="test",
        )

        self.lya = User.objects.create_user(
            username="Lya",
            password="test",
        )

    def test_pre_founder_operator_posts_count_as_development_activity(self):
        as_of = timezone.now()

        # Founder is newly created today.
        founder = FounderAccount.objects.create(
            handle="lya",
            owner_root=self.dj,
            current_account=self.lya,
            status=FounderAccount.STATUS_OWNED,
        )

        # Simulate 13 public posts over the preceding 14 days.
        for index in range(13):
            post = FeedPost.objects.create(
                user=self.lya,
                title=f"Post {index}",
                content=f"Development post {index}",
                is_public=True,
            )

            FeedPost.objects.filter(
                pk=post.pk
            ).update(
                created_at=(
                    as_of
                    - timedelta(days=14 - index)
                )
            )

        valuation = get_founder_valuation(
            founder,
            as_of=as_of,
        )

        development = valuation["development"]

        # Ownership clock remains tied to the new Founder.
        self.assertEqual(
            development["ownership_days"],
            0,
        )

        # Operator activity predating Founder creation counts.
        self.assertEqual(
            development["public_posts"],
            13,
        )

        self.assertGreater(
            development["posts_per_week"],
            3.0,
        )

        # Posting activity alone cannot bypass the 182-day
        # Founder holding requirement.
        self.assertFalse(
            development["active_development"]
        )

    def test_private_posts_do_not_count(self):
        as_of = timezone.now()

        founder = FounderAccount.objects.create(
            handle="ruby",
            owner_root=self.dj,
            current_account=self.lya,
            status=FounderAccount.STATUS_OWNED,
        )

        FeedPost.objects.create(
            user=self.lya,
            title="Private",
            content="Private development post",
            is_public=False,
        )

        valuation = get_founder_valuation(
            founder,
            as_of=as_of,
        )

        self.assertEqual(
            valuation["development"]["public_posts"],
            0,
        )
        self.assertEqual(
            valuation["development"]["posts_per_week"],
            0.0,
        )
