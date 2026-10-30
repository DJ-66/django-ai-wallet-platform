"""Reservation isolation tests for FANZ AI publications."""

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from auctions.models import ScheduledPublication
from auctions.ai_services.legacy_publication_reservation import (
    PREPARING_MARKER,
    is_ai_preparation_reservation,
    creator_has_active_ai_publication,
)


class LegacyPublicationReservationTests(TestCase):

    def setUp(self):
        self.creator = get_user_model().objects.create_user(
            username="ReservationCreatorTest",
            password="test-only-password",
        )

    def make_publication(self, *, key, status, marker=""):
        return ScheduledPublication.objects.create(
            publication_key=key,
            creator=self.creator,
            source_path="creator/test.jpg",
            content="Test caption\n\n#FANZ",
            campaign_key=marker,
            scheduled_for=timezone.now(),
            status=status,
        )

    def test_preparation_reservation_blocks_scheduling(self):
        publication = self.make_publication(
            key="ai:reservation:test",
            status=ScheduledPublication.STATUS_DRAFT,
            marker=PREPARING_MARKER,
        )

        self.assertTrue(
            is_ai_preparation_reservation(publication)
        )
        self.assertTrue(
            creator_has_active_ai_publication(self.creator)
        )

    def test_rehearsal_draft_does_not_block(self):
        publication = self.make_publication(
            key="rehearsal:test",
            status=ScheduledPublication.STATUS_DRAFT,
        )

        self.assertFalse(
            is_ai_preparation_reservation(publication)
        )
        self.assertFalse(
            creator_has_active_ai_publication(self.creator)
        )

    def test_queued_ai_publication_blocks(self):
        self.make_publication(
            key="ai:queued:test",
            status=ScheduledPublication.STATUS_QUEUED,
        )

        self.assertTrue(
            creator_has_active_ai_publication(self.creator)
        )

    def test_failed_ai_publication_does_not_block(self):
        self.make_publication(
            key="ai:failed:test",
            status=ScheduledPublication.STATUS_FAILED,
        )

        self.assertFalse(
            creator_has_active_ai_publication(self.creator)
        )


class AtomicAIReservationTests(TestCase):
    """Verify reservation behavior before scheduler integration."""

    def setUp(self):
        self.creator = get_user_model().objects.create_user(
            username="AtomicReservationTest",
            password="test-only-password",
        )

    def reserve(self, key):
        from auctions.ai_services.legacy_publication_reservation import (
            reserve_ai_publication,
        )

        return reserve_ai_publication(
            creator=self.creator,
            publication_key=key,
            source_path="creator/test.jpg",
            scheduled_for=timezone.now(),
            title="Reservation test",
            content="Test caption\n\n#FANZ",
        )

    def test_second_reservation_is_rejected(self):
        first = self.reserve("ai:atomic:first")

        self.assertIsNotNone(first)
        self.assertEqual(
            first.status,
            ScheduledPublication.STATUS_DRAFT,
        )
        self.assertEqual(first.campaign_key, PREPARING_MARKER)

        second = self.reserve("ai:atomic:second")

        self.assertIsNone(second)

        self.assertEqual(
            ScheduledPublication.objects.filter(
                creator=self.creator,
                publication_key__startswith="ai:",
            ).count(),
            1,
        )

    def test_existing_queued_post_blocks_reservation(self):
        ScheduledPublication.objects.create(
            publication_key="ai:atomic:queued",
            creator=self.creator,
            source_path="creator/existing.jpg",
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        result = self.reserve("ai:atomic:new")

        self.assertIsNone(result)

        self.assertEqual(
            ScheduledPublication.objects.filter(
                creator=self.creator,
                publication_key__startswith="ai:",
            ).count(),
            1,
        )


class ConcurrentAIReservationTests(TransactionTestCase):
    """Verify competing PostgreSQL reservations."""

    def test_two_workers_reserve_only_one_publication(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections

        from auctions.ai_services.legacy_publication_reservation import (
            reserve_ai_publication,
        )

        creator = get_user_model().objects.create_user(
            username="ConcurrentReservationTest",
            password="test-only-password",
        )

        barrier = Barrier(2)

        def attempt(number):
            close_old_connections()

            try:
                barrier.wait(timeout=10)

                return reserve_ai_publication(
                    creator=creator,
                    publication_key=f"ai:concurrent:{number}",
                    source_path=f"creator/{number}.jpg",
                    scheduled_for=timezone.now(),
                    title="Concurrent reservation",
                    content="Test caption\n\n#FANZ",
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt, number)
                for number in (1, 2)
            ]

            results = [
                future.result(timeout=20)
                for future in futures
            ]

        successful = [
            result
            for result in results
            if result is not None
        ]

        self.assertEqual(len(successful), 1)

        reservations = ScheduledPublication.objects.filter(
            creator=creator,
            publication_key__startswith="ai:",
        )

        self.assertEqual(reservations.count(), 1)

        reservation = reservations.get()

        self.assertEqual(
            reservation.status,
            ScheduledPublication.STATUS_DRAFT,
        )
        self.assertEqual(
            reservation.campaign_key,
            PREPARING_MARKER,
        )

        print("Concurrent workers: 2")
        print("Successful reservations: 1")
        print("Duplicate publications: 0")
        print("PostgreSQL concurrency: PASS")


class AIReservationFinalizationTests(TestCase):
    """Tokenless finalization must never be permitted."""

    def test_tokenless_finalization_rejected(self):
        from auctions.ai_services.legacy_publication_reservation import (
            finalize_ai_publication_reservation,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Tokenless AI reservation finalization is disabled",
        ):
            finalize_ai_publication_reservation(
                reservation_id=1,
                content="Test caption",
                marker="ai_gemma4",
            )




class AIReservationLeaseTests(TestCase):
    """Verify lease ownership, expiration and stale-token rejection."""

    def setUp(self):
        from auctions.ai_services.legacy_publication_reservation import (
            reserve_ai_publication,
        )

        self.creator = get_user_model().objects.create_user(
            username="LeaseOwnershipTest",
            password="test-only-password",
        )

        self.reservation = reserve_ai_publication(
            creator=self.creator,
            publication_key="ai:lease:test",
            source_path="creator/image.jpg",
            scheduled_for=timezone.now(),
            title="Lease test",
            content="Original caption\n\n#Fashion #FANZ",
        )

        self.assertIsNotNone(self.reservation)

    def test_claim_creates_valid_lease(self):
        from auctions.ai_services.legacy_publication_reservation import (
            claim_ai_reservation,
            verify_ai_reservation_claim,
        )

        result = claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNotNone(result)

        publication_id, token = result

        self.assertEqual(publication_id, self.reservation.pk)
        self.assertTrue(
            verify_ai_reservation_claim(publication_id, token)
        )

    def test_active_lease_blocks_second_claim(self):
        from auctions.ai_services.legacy_publication_reservation import (
            claim_ai_reservation,
        )

        first = claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        second = claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_expired_lease_reclaims_and_rejects_old_token(self):
        from datetime import timedelta

        from auctions.models import LegacyAIPublicationLease
        from auctions.ai_services.legacy_publication_reservation import (
            claim_ai_reservation,
            verify_ai_reservation_claim,
        )

        first = claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNotNone(first)
        _, old_token = first

        lease = LegacyAIPublicationLease.objects.get(
            publication=self.reservation,
        )

        lease.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        lease.save(update_fields=["lease_expires_at"])

        second = claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNotNone(second)

        _, new_token = second

        self.assertNotEqual(old_token, new_token)

        self.assertFalse(
            verify_ai_reservation_claim(
                self.reservation.pk,
                old_token,
            )
        )

        self.assertTrue(
            verify_ai_reservation_claim(
                self.reservation.pk,
                new_token,
            )
        )


class ClaimedAIReservationFinalizationTests(TestCase):
    """Only the current lease owner may queue an AI publication."""

    def setUp(self):
        from auctions.ai_services.legacy_publication_reservation import (
            reserve_ai_publication,
        )

        self.creator = get_user_model().objects.create_user(
            username="ClaimedFinalizationTest",
            password="test-only-password",
        )

        self.reservation = reserve_ai_publication(
            creator=self.creator,
            publication_key="ai:claimed-finalization:test",
            source_path="creator/image.jpg",
            scheduled_for=timezone.now(),
            title="Claimed finalization",
            content="Original caption\n\n#Fashion #FANZ",
        )

        self.assertIsNotNone(self.reservation)

        self.prepared = (
            "Original caption\n"
            "Tell me your favorite story in my DMs."
            "\n\n#Fashion #FANZ"
        )

    def claim(self):
        from auctions.ai_services.legacy_publication_reservation import (
            claim_ai_reservation,
        )

        return claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

    def finalize(self, token):
        from auctions.ai_services.legacy_publication_reservation import (
            finalize_claimed_ai_reservation,
        )

        return finalize_claimed_ai_reservation(
            reservation_id=self.reservation.pk,
            token=token,
            content=self.prepared,
            marker="ai_gemma4",
        )

    def expire(self):
        from datetime import timedelta
        from auctions.models import LegacyAIPublicationLease

        lease = LegacyAIPublicationLease.objects.get(
            publication=self.reservation,
        )

        lease.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        lease.save(update_fields=["lease_expires_at"])

    def test_current_owner_can_finalize(self):
        _, token = self.claim()

        self.assertTrue(self.finalize(token))

        self.reservation.refresh_from_db()

        self.assertEqual(
            self.reservation.status,
            ScheduledPublication.STATUS_QUEUED,
        )
        self.assertEqual(
            self.reservation.campaign_key,
            "ai_gemma4",
        )
        self.assertEqual(
            self.reservation.content,
            self.prepared,
        )

    def test_expired_owner_cannot_finalize(self):
        _, token = self.claim()
        self.expire()

        self.assertFalse(self.finalize(token))

        self.reservation.refresh_from_db()

        self.assertEqual(
            self.reservation.status,
            ScheduledPublication.STATUS_DRAFT,
        )

    def test_reclaimed_owner_rejects_old_token(self):
        _, old_token = self.claim()
        self.expire()

        _, new_token = self.claim()

        self.assertNotEqual(old_token, new_token)
        self.assertFalse(self.finalize(old_token))
        self.assertTrue(self.finalize(new_token))

    def test_duplicate_finalization_rejected(self):
        _, token = self.claim()

        self.assertTrue(self.finalize(token))
        self.assertFalse(self.finalize(token))


class AIReservationFailureRecoveryTests(TestCase):
    """Verify lease-aware Gemma failure recovery."""

    def setUp(self):
        from auctions.ai_services.legacy_publication_reservation import (
            reserve_ai_publication,
            claim_ai_reservation,
        )

        self.creator = get_user_model().objects.create_user(
            username="FailureRecoveryLeaseTest",
            password="test-only-password",
        )

        self.reservation = reserve_ai_publication(
            creator=self.creator,
            publication_key="ai:failure-recovery:test",
            source_path="creator/image.jpg",
            scheduled_for=timezone.now(),
            title="Recovery test",
            content="Original caption\n\n#Fashion #FANZ",
        )

        self.assertIsNotNone(self.reservation)

        self.claim_ai_reservation = claim_ai_reservation

        self.claim = claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNotNone(self.claim)
        self.token = self.claim[1]

    def fail(self, token=None):
        from auctions.ai_services.legacy_publication_reservation import (
            fail_ai_reservation_claim,
        )

        return fail_ai_reservation_claim(
            reservation_id=self.reservation.pk,
            token=self.token if token is None else token,
            error="Simulated Gemma timeout",
        )

    def test_failure_records_cooldown(self):
        from auctions.models import LegacyAIPublicationLease

        self.assertTrue(self.fail())

        lease = LegacyAIPublicationLease.objects.get(
            publication=self.reservation,
        )

        self.assertEqual(lease.attempt_count, 1)
        self.assertIn("Gemma timeout", lease.last_error)
        self.assertIsNotNone(lease.next_retry_at)
        self.assertIsNone(lease.claim_token)

        self.reservation.refresh_from_db()

        self.assertEqual(
            self.reservation.status,
            ScheduledPublication.STATUS_DRAFT,
        )
        self.assertEqual(
            self.reservation.campaign_key,
            PREPARING_MARKER,
        )

    def test_cooldown_blocks_immediate_retry(self):
        self.assertTrue(self.fail())

        second = self.claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNone(second)

    def test_retry_after_cooldown(self):
        from datetime import timedelta
        from auctions.models import LegacyAIPublicationLease

        self.assertTrue(self.fail())

        lease = LegacyAIPublicationLease.objects.get(
            publication=self.reservation,
        )

        lease.next_retry_at = (
            timezone.now() - timedelta(seconds=1)
        )
        lease.save(update_fields=["next_retry_at"])

        second = self.claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNotNone(second)
        self.assertNotEqual(self.token, second[1])

    def test_stale_worker_cannot_record_failure(self):
        from datetime import timedelta
        from uuid import uuid4

        from auctions.models import LegacyAIPublicationLease

        lease = LegacyAIPublicationLease.objects.get(
            publication=self.reservation,
        )

        lease.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        lease.save(update_fields=["lease_expires_at"])

        new_claim = self.claim_ai_reservation(
            reservation_id=self.reservation.pk,
        )

        self.assertIsNotNone(new_claim)
        new_token = new_claim[1]

        self.assertFalse(self.fail(self.token))
        self.assertFalse(self.fail(uuid4()))

        lease.refresh_from_db()

        self.assertEqual(lease.claim_token, new_token)
        self.assertEqual(lease.attempt_count, 0)
        self.assertIsNone(lease.next_retry_at)


class AIReservationDiscoveryTests(TestCase):
    """Verify automatic discovery of recoverable AI drafts."""

    def setUp(self):
        from auctions.ai_services.legacy_publication_reservation import (
            reserve_ai_publication,
        )

        self.creator = get_user_model().objects.create_user(
            username="DraftDiscoveryTest",
            password="test-only-password",
        )

        self.reservation = reserve_ai_publication(
            creator=self.creator,
            publication_key="ai:discovery:original",
            source_path="creator/original.jpg",
            scheduled_for=timezone.now(),
            title="Original reservation",
            content="Original caption\n\n#Fashion #FANZ",
        )

        self.assertIsNotNone(self.reservation)

    def discover(self):
        from auctions.ai_services.legacy_publication_reservation import (
            claim_existing_ai_preparation,
        )

        return claim_existing_ai_preparation(
            creator=self.creator,
        )

    def test_unclaimed_draft_is_discovered(self):
        claim = self.discover()

        self.assertIsNotNone(claim)
        self.assertEqual(claim[0], self.reservation.pk)

        self.reservation.refresh_from_db()
        self.assertEqual(
            self.reservation.publication_key,
            "ai:discovery:original",
        )
        self.assertEqual(
            self.reservation.source_path,
            "creator/original.jpg",
        )

    def test_active_lease_blocks_discovery(self):
        first = self.discover()
        self.assertIsNotNone(first)

        second = self.discover()
        self.assertIsNone(second)

    def test_expired_lease_reclaims_same_draft(self):
        from datetime import timedelta
        from auctions.models import LegacyAIPublicationLease
        from auctions.ai_services.legacy_publication_reservation import (
            verify_ai_reservation_claim,
        )

        first = self.discover()
        self.assertIsNotNone(first)

        lease = LegacyAIPublicationLease.objects.get(
            publication=self.reservation,
        )
        lease.lease_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        lease.save(update_fields=["lease_expires_at"])

        second = self.discover()

        self.assertIsNotNone(second)
        self.assertEqual(second[0], first[0])
        self.assertNotEqual(second[1], first[1])

        self.assertFalse(
            verify_ai_reservation_claim(
                self.reservation.pk,
                first[1],
            )
        )
        self.assertTrue(
            verify_ai_reservation_claim(
                self.reservation.pk,
                second[1],
            )
        )

        self.assertEqual(
            ScheduledPublication.objects.filter(
                creator=self.creator,
                publication_key__startswith="ai:",
            ).count(),
            1,
        )
