"""Verify FANZ AI publication sequence consistency."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.models import ScheduledPublication
from auctions.ai_services.legacy_suffix_adapter import (
    next_publication_sequence,
    publication_sequence,
)
from auctions.ai_services.legacy_publication_preparation import (
    plan_publication_ending,
)


class LegacySequenceConsistencyTests(TestCase):

    def test_failed_history_counts_toward_fourth_cta(self):
        user = get_user_model().objects.create_user(
            username="SequenceConsistencyTest",
            password="test-only-password",
        )

        now = timezone.now()

        for number, status in (
            (1, ScheduledPublication.STATUS_QUEUED),
            (2, ScheduledPublication.STATUS_FAILED),
            (3, ScheduledPublication.STATUS_QUEUED),
        ):
            ScheduledPublication.objects.create(
                publication_key=f"ai:sequence:test-{number}",
                creator=user,
                source_path=f"history/{number}.jpg",
                content="Historical caption\n\n#FANZ",
                scheduled_for=now + timedelta(minutes=number),
                status=status,
            )

        scheduled_for = now + timedelta(minutes=4)

        scheduler_sequence = next_publication_sequence(
            creator_id=user.pk,
            scheduled_for=scheduled_for,
        )

        fourth = ScheduledPublication.objects.create(
            publication_key="ai:sequence:test-4",
            creator=user,
            source_path="creator/fourth.jpg",
            content="Fourth caption\n\n#FANZ",
            scheduled_for=scheduled_for,
            status=ScheduledPublication.STATUS_QUEUED,
        )

        publisher_sequence = publication_sequence(fourth)

        self.assertEqual(scheduler_sequence, 4)
        self.assertEqual(publisher_sequence, 4)

        plan = plan_publication_ending(
            username=user.username,
            publication_key=fourth.publication_key,
            sequence=publisher_sequence,
        )

        self.assertEqual(plan.kind, "cta")
        self.assertEqual(plan.suffix.campaign, "founder")

        print("Failed history counted: PASS")
        print("Scheduler/publisher agreement: PASS")
        print("Fourth publication Founder CTA: PASS")
