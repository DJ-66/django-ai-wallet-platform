"""Tests for lease-protected FANZ AI caption preparation."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.models import (
    LegacyAIPublicationLease,
    ScheduledPublication,
)
from auctions.ai_services.legacy_publication_reservation import (
    reserve_ai_publication,
    claim_ai_reservation,
)
from auctions.ai_services.legacy_claimed_preparation import (
    prepare_claimed_ai_publication,
)
from auctions.ai_services.legacy_gemma_closer import CreativeCloserError


class ClaimedPreparationTests(TestCase):

    def setUp(self):
        self.creator = get_user_model().objects.create_user(
            username="ClaimedPreparationTest",
            password="test-only-password",
        )

        self.reservation = reserve_ai_publication(
            creator=self.creator,
            publication_key="ai:claimed-preparation:test",
            source_path="creator/image.jpg",
            scheduled_for=timezone.now(),
            title="Preparation test",
            content="A little chaos today.\n\n#Fashion #FANZ",
        )

        self.assertIsNotNone(self.reservation)

        claim = claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNotNone(claim)
        self.token = claim[1]

    def prepare(self):
        return prepare_claimed_ai_publication(
            reservation_id=self.reservation.pk,
            token=self.token,
            bio="Playful fictional creator",
        )

    @patch(
        "auctions.ai_services.legacy_claimed_preparation."
        "prepare_ai_caption"
    )
    def test_successful_preparation(self, generate):
        from auctions.ai_services.legacy_publication_preparation import (
            plan_publication_ending,
        )

        plan = plan_publication_ending(
            username=self.creator.username,
            publication_key=self.reservation.publication_key,
            sequence=1,
        )

        generate.return_value = (
            "A little chaos today.\n"
            "Tell me your story in my DMs."
            "\n\n#Fashion #FANZ",
            plan,
        )

        self.assertTrue(self.prepare())

        self.reservation.refresh_from_db()

        self.assertEqual(
            self.reservation.status,
            ScheduledPublication.STATUS_QUEUED,
        )
        self.assertEqual(
            self.reservation.campaign_key,
            "ai_gemma4",
        )

    @patch(
        "auctions.ai_services.legacy_claimed_preparation."
        "prepare_ai_caption"
    )
    def test_generation_failure_records_cooldown(self, generate):
        generate.side_effect = CreativeCloserError(
            "Simulated Gemma timeout"
        )

        with self.assertRaises(CreativeCloserError):
            self.prepare()

        lease = LegacyAIPublicationLease.objects.get(
            publication=self.reservation,
        )

        self.assertEqual(lease.attempt_count, 1)
        self.assertIsNotNone(lease.next_retry_at)
        self.assertIsNone(lease.claim_token)

        self.reservation.refresh_from_db()
        self.assertEqual(
            self.reservation.status,
            ScheduledPublication.STATUS_DRAFT,
        )

    @patch(
        "auctions.ai_services.legacy_claimed_preparation."
        "prepare_ai_caption"
    )
    def test_expired_lease_cannot_finalize(self, generate):
        from auctions.ai_services.legacy_publication_preparation import (
            plan_publication_ending,
        )

        plan = plan_publication_ending(
            username=self.creator.username,
            publication_key=self.reservation.publication_key,
            sequence=1,
        )

        def expire_during_generation(**kwargs):
            lease = LegacyAIPublicationLease.objects.get(
                publication=self.reservation,
            )
            lease.lease_expires_at = (
                timezone.now() - timedelta(seconds=1)
            )
            lease.save(update_fields=["lease_expires_at"])

            return (
                "A little chaos today.\n"
                "Tell me your story in my DMs."
                "\n\n#Fashion #FANZ",
                plan,
            )

        generate.side_effect = expire_during_generation

        self.assertFalse(self.prepare())

        self.reservation.refresh_from_db()

        self.assertEqual(
            self.reservation.status,
            ScheduledPublication.STATUS_DRAFT,
        )
        self.assertEqual(
            self.reservation.campaign_key,
            "ai_preparing",
        )
