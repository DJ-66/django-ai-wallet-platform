import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services import creator_caption_recovery as recovery
from auctions.models import (
    CreatorCaptionRecoveryState,
    FeedPost,
    ScheduledPublication,
)


User = get_user_model()


class CreatorCaptionRecoveryClaimTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.manifest = Path(self.tempdir.name) / "manifest.json"
        self.manifest.write_text(json.dumps({
            "creators": [
                {"account": "CreatorA"},
                {"account": "CreatorB"},
            ],
        }))

        self.creator_a = User.objects.create_user(
            username="CreatorA",
        )
        self.creator_b = User.objects.create_user(
            username="CreatorB",
        )
        self.outsider = User.objects.create_user(
            username="Outsider",
        )

        self.now = timezone.now()

    def publication(self, creator, number, status="queued"):
        published = (
            status == ScheduledPublication.STATUS_PUBLISHED
        )

        feed = None

        if published:
            feed = FeedPost.objects.create(
                user=creator,
                title="From the Collection",
                content="A new favorite from the collection.",
            )

        return ScheduledPublication.objects.create(
            publication_key=f"ai:{creator.username.lower()}:{number}",
            creator=creator,
            source_path=f"post-{number}.jpg",
            title="From the Collection",
            content="A new favorite from the collection.",
            scheduled_for=self.now + timedelta(hours=number),
            status=status,
            feed_post=feed,
            published_at=self.now if published else None,
        )

    def claim(self):
        with patch(
            "auctions.management.commands."
            "generate_ai_publications.MANIFEST_PATH",
            self.manifest,
        ):
            return recovery.claim_next_publication()

    def test_queued_priority_and_distinct_claims(self):
        published = self.publication(
            self.creator_a, 1,
            status="published",
        )
        queued = self.publication(self.creator_b, 2)

        first = self.claim()
        self.assertEqual(first[0], queued.pk)

        second = self.claim()
        self.assertEqual(second[0], published.pk)

        self.assertIsNone(self.claim())


    def test_queued_only_never_claims_published_posts(self):
        published = self.publication(
            self.creator_a,
            1,
            status="published",
        )

        with patch(
            "auctions.management.commands."
            "generate_ai_publications.MANIFEST_PATH",
            self.manifest,
        ):
            result = recovery.claim_next_publication(
                queued_only=True,
            )

        self.assertIsNone(result)

        self.assertFalse(
            CreatorCaptionRecoveryState.objects.filter(
                publication=published,
            ).exists()
        )

        # Existing default behavior remains supported.
        self.assertEqual(
            self.claim()[0],
            published.pk,
        )


    def test_published_only_never_claims_queued_posts(self):
        queued = self.publication(self.creator_a, 1)
        published = self.publication(
            self.creator_b,
            2,
            status="published",
        )

        with patch(
            "auctions.management.commands."
            "generate_ai_publications.MANIFEST_PATH",
            self.manifest,
        ):
            result = recovery.claim_next_publication(
                published_only=True,
            )

        self.assertEqual(result[0], published.pk)
        self.assertFalse(
            CreatorCaptionRecoveryState.objects.filter(
                publication=queued,
            ).exists()
        )

    def test_conflicting_scope_flags_are_rejected(self):
        with self.assertRaises(ValueError):
            recovery.claim_next_publication(
                queued_only=True,
                published_only=True,
            )

    def test_queued_claim_respects_minimum_lead_time(self):
        near = self.publication(self.creator_a, 1)
        far = self.publication(self.creator_b, 2)

        near.scheduled_for = (
            timezone.now() + timedelta(minutes=20)
        )
        near.save(update_fields=["scheduled_for"])

        far.scheduled_for = (
            timezone.now() + timedelta(hours=3)
        )
        far.save(update_fields=["scheduled_for"])

        with patch(
            "auctions.management.commands."
            "generate_ai_publications.MANIFEST_PATH",
            self.manifest,
        ):
            first = recovery.claim_next_publication(
                queued_only=True,
                min_lead_minutes=45,
            )
            second = recovery.claim_next_publication(
                queued_only=True,
                min_lead_minutes=45,
            )

        self.assertEqual(first[0], far.pk)
        self.assertIsNone(second)

        self.assertFalse(
            CreatorCaptionRecoveryState.objects.filter(
                publication=near,
            ).exists()
        )

    def test_completed_publication_is_skipped(self):
        completed = self.publication(self.creator_a, 1)
        available = self.publication(self.creator_b, 2)

        CreatorCaptionRecoveryState.objects.create(
            publication=completed,
            status=CreatorCaptionRecoveryState.STATUS_COMPLETED,
            completed_at=self.now,
        )

        claimed = self.claim()
        self.assertEqual(claimed[0], available.pk)

    def test_active_lease_blocks_duplicate_claim(self):
        publication = self.publication(self.creator_a, 1)

        first = self.claim()
        self.assertEqual(first[0], publication.pk)

        self.assertTrue(
            recovery.verify_claim(*first)
        )
        self.assertIsNone(self.claim())

    def test_expired_lease_can_be_reclaimed(self):
        publication = self.publication(self.creator_a, 1)

        first = self.claim()

        state = CreatorCaptionRecoveryState.objects.get(
            publication=publication,
        )
        state.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        state.save(update_fields=["lease_expires_at"])

        second = self.claim()

        self.assertEqual(second[0], publication.pk)
        self.assertNotEqual(first[1], second[1])
        self.assertFalse(recovery.verify_claim(*first))
        self.assertTrue(recovery.verify_claim(*second))

    def test_failed_claim_respects_retry_cooldown(self):
        publication = self.publication(self.creator_a, 1)

        claimed = self.claim()

        self.assertTrue(
            recovery.mark_recovery_failed(
                *claimed,
                "temporary inference failure",
            )
        )

        state = CreatorCaptionRecoveryState.objects.get(
            publication=publication,
        )

        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_FAILED,
        )
        self.assertEqual(state.attempt_count, 1)
        self.assertGreater(
            state.next_retry_at,
            timezone.now(),
        )
        self.assertIsNone(self.claim())

    def test_old_token_cannot_fail_reclaimed_claim(self):
        publication = self.publication(self.creator_a, 1)

        first = self.claim()

        state = CreatorCaptionRecoveryState.objects.get(
            publication=publication,
        )
        state.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        state.save(update_fields=["lease_expires_at"])

        second = self.claim()

        self.assertEqual(second[0], publication.pk)
        self.assertNotEqual(first[1], second[1])

        self.assertFalse(
            recovery.mark_recovery_failed(
                *first,
                "stale worker failure",
            )
        )

        state.refresh_from_db()

        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_PROCESSING,
        )
        self.assertEqual(state.claim_token, second[1])
        self.assertEqual(state.attempt_count, 0)
        self.assertTrue(recovery.verify_claim(*second))

    def test_expired_token_cannot_mark_failure(self):
        publication = self.publication(self.creator_a, 1)

        claimed = self.claim()

        state = CreatorCaptionRecoveryState.objects.get(
            publication=publication,
        )
        state.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        state.save(update_fields=["lease_expires_at"])

        self.assertFalse(
            recovery.verify_claim(*claimed)
        )

        self.assertFalse(
            recovery.mark_recovery_failed(
                *claimed,
                "late inference failure",
            )
        )

        state.refresh_from_db()

        self.assertEqual(
            state.status,
            CreatorCaptionRecoveryState.STATUS_PROCESSING,
        )
        self.assertEqual(state.attempt_count, 0)

    def test_unapproved_creator_is_skipped(self):
        outsider = self.publication(self.outsider, 1)
        approved = self.publication(self.creator_a, 2)

        claimed = self.claim()

        self.assertEqual(claimed[0], approved.pk)
        self.assertFalse(
            CreatorCaptionRecoveryState.objects.filter(
                publication=outsider,
            ).exists()
        )
