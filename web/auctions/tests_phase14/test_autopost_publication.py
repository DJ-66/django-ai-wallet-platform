"""Database constraints for persistent AutoPost reservations."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from auctions.models import (
    AutoPostConfiguration,
    AutoPostPublication,
    PlatformMediaAsset,
)


class AutoPostPublicationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.account = User.objects.create_user(
            username="autopost_reservation_test",
        )
        self.other_account = User.objects.create_user(
            username="autopost_other_account",
        )

        self.config = AutoPostConfiguration.objects.create(
            account=self.account,
        )
        self.other_config = AutoPostConfiguration.objects.create(
            account=self.other_account,
        )

        self.asset = PlatformMediaAsset.objects.create(
            account=self.account,
            sha256="a" * 64,
            image="platform_media/test-image.webp",
        )

        self.other_asset = PlatformMediaAsset.objects.create(
            account=self.other_account,
            sha256="b" * 64,
            image="platform_media/other-image.webp",
        )

    def reserve(self, **overrides):
        values = {
            "configuration": self.config,
            "publication_key": "autopost:reservation:1",
            "sequence_number": 1,
            "media_asset": self.asset,
            "scheduled_for": timezone.now() + timedelta(hours=36),
            "personality": "snarky",
        }
        values.update(overrides)
        return AutoPostPublication.objects.create(**values)

    def test_reservation_defaults_to_inert_state(self):
        reservation = self.reserve()

        self.assertEqual(
            reservation.status,
            AutoPostPublication.STATUS_RESERVED,
        )
        self.assertIsNone(reservation.scheduled_publication_id)
        self.assertIsNone(reservation.translations)

    def test_duplicate_sequence_rejected_for_same_account(self):
        self.reserve()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.reserve(
                    publication_key="autopost:reservation:2",
                )

    def test_same_sequence_allowed_for_different_accounts(self):
        self.reserve()
        other = self.reserve(
            configuration=self.other_config,
            publication_key="autopost:other:1",
            media_asset=self.other_asset,
        )

        self.assertEqual(other.sequence_number, 1)

    def test_duplicate_publication_key_rejected(self):
        self.reserve()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.reserve(sequence_number=2)

    def test_zero_sequence_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.reserve(sequence_number=0)

    def test_reservation_does_not_create_feed_post(self):
        from auctions.models import FeedPost, ScheduledPublication

        self.reserve()

        self.assertEqual(FeedPost.objects.count(), 0)
        self.assertEqual(ScheduledPublication.objects.count(), 0)
