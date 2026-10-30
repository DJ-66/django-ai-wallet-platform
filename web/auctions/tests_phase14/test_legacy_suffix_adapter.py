"""Database-backed tests for legacy AI suffix selection."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.models import ScheduledPublication
from auctions.ai_services.legacy_suffix_adapter import (
    FLAG,
    suffix_context_for_publication,
)


class LegacySuffixAdapterTests(TestCase):

    def test_sequence_flag_and_non_ai_exclusion(self):
        user = get_user_model().objects.create_user(
            username="SuffixTestCreator",
            password="test-only-password",
        )

        base = timezone.now()

        def make_post(number, key):
            return ScheduledPublication.objects.create(
                creator=user,
                publication_key=key,
                source_path=f"test/image-{number}.jpg",
                title="Test title",
                content="Test caption\n\n#Fashion #FANZ",
                scheduled_for=base + timedelta(days=number),
                status=ScheduledPublication.STATUS_QUEUED,
            )

        first = make_post(1, "ai:test:1")
        second = make_post(2, "ai:test:2")
        third = make_post(3, "ai:test:3")
        fourth = make_post(5, "ai:test:5")
        unrelated = make_post(4, "other:test:4")

        with patch.dict("os.environ", {FLAG: "false"}):
            self.assertIsNone(
                suffix_context_for_publication(third)
            )

        with patch.dict("os.environ", {FLAG: "true"}):
            self.assertIsNone(
                suffix_context_for_publication(unrelated)
            )

            self.assertEqual(
                suffix_context_for_publication(first)["sequence"],
                1,
            )

            self.assertEqual(
                suffix_context_for_publication(second)["sequence"],
                2,
            )

            result = suffix_context_for_publication(fourth)

            self.assertEqual(result["sequence"], 4)
            self.assertEqual(result["suffix"].campaign, "founder")
            self.assertEqual(
                result["destination"].campaign,
                "founder",
            )
