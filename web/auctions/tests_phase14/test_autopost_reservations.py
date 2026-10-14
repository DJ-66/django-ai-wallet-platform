"""Transactional reservation tests for FANZ AutoPost."""

from datetime import timedelta
from tempfile import TemporaryDirectory
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from auctions.ai_services.autopost_reservations import reserve_autopost
from auctions.models import AutoPostConfiguration, AutoPostPublication, PlatformMediaAsset


class AutoPostReservationTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media_override = override_settings(MEDIA_ROOT=self.temp.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

        self.account = get_user_model().objects.create_user(
            username="autopost_reserve_creator",
        )
        self.config = AutoPostConfiguration.objects.create(
            account=self.account,
            enabled=True,
            personality="snarky",
            cta_every=3,
            enabled_campaigns=["founder", "credits", "autopost"],
        )

        self.assets = []
        for index in range(2):
            asset = PlatformMediaAsset(
                account=self.account,
                sha256=str(index) * 64,
                display_order=index,
            )
            asset.image.save(
                f"asset-{index}.webp",
                ContentFile(b"mock-media"),
                save=True,
            )
            self.assets.append(asset)

        self.when = timezone.now() + timedelta(days=3)

    def reserve(self, key, **kwargs):
        return reserve_autopost(
            account_id=self.account.pk,
            request_key=key,
            scheduled_for=kwargs.get("scheduled_for", self.when),
        )

    def test_first_reservation(self):
        item = self.reserve("first")
        self.assertEqual(item.sequence_number, 1)
        self.assertEqual(item.media_asset_id, self.assets[0].pk)
        self.assertEqual(item.status, "reserved")
        self.assertIsNone(item.scheduled_publication_id)
        self.assertEqual(
            set(item.suffix_translations),
            {"en", "es", "pt"},
        )
        self.assertTrue(all(item.suffix_translations.values()))

    def test_duplicate_request_is_idempotent(self):
        first = self.reserve("first")
        again = self.reserve("first")
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(AutoPostPublication.objects.count(), 1)
        self.config.refresh_from_db()
        self.assertEqual(self.config.next_sequence, 2)

    def test_rotation_advances(self):
        first = self.reserve("first")
        second = self.reserve(
            "second",
            scheduled_for=self.when + timedelta(hours=36),
        )
        self.assertEqual(
            [first.media_asset_id, second.media_asset_id],
            [self.assets[0].pk, self.assets[1].pk],
        )
        self.assertEqual(
            [first.sequence_number, second.sequence_number],
            [1, 2],
        )

    def test_disabled_account_rejected(self):
        self.config.enabled = False
        self.config.save(update_fields=["enabled"])

        with self.assertRaises(ValidationError):
            self.reserve("first")

        self.assertFalse(AutoPostPublication.objects.exists())

    def test_missing_media_rolls_back_counters(self):
        self.assets[0].image.storage.delete(
            self.assets[0].image.name
        )

        with self.assertRaises(ValidationError):
            self.reserve("first")

        self.config.refresh_from_db()
        self.assertEqual(self.config.next_sequence, 1)
        self.assertEqual(self.config.next_media_index, 0)
        self.assertFalse(AutoPostPublication.objects.exists())

    def test_rejects_posts_closer_than_configured_interval(self):
        self.reserve("first")

        with self.assertRaises(ValidationError):
            self.reserve(
                "too-soon",
                scheduled_for=self.when + timedelta(hours=24),
            )

        self.config.refresh_from_db()
        self.assertEqual(self.config.next_sequence, 2)
        self.assertEqual(AutoPostPublication.objects.count(), 1)

    def test_reserved_suffix_survives_settings_change(self):
        reservation = self.reserve("snapshot-test")

        original = dict(reservation.suffix_translations)
        original_personality = reservation.personality
        original_campaign = reservation.campaign
        original_destination = reservation.destination_url
        original_media_id = reservation.media_asset_id

        self.config.personality = "dominatrix"
        self.config.cta_every = 1
        self.config.enabled_campaigns = ["credits"]
        self.config.save(update_fields=[
            "personality",
            "cta_every",
            "enabled_campaigns",
        ])

        reservation.refresh_from_db()

        self.assertEqual(reservation.suffix_translations, original)
        self.assertEqual(reservation.personality, original_personality)
        self.assertEqual(reservation.campaign, original_campaign)
        self.assertEqual(reservation.destination_url, original_destination)
        self.assertEqual(reservation.media_asset_id, original_media_id)

    def test_custom_business_campaign_is_frozen(self):
        self.config.cta_every = 1
        self.config.enabled_campaigns = ["custom"]
        self.config.custom_cta_title = (
            "Visit my photography shop 📸"
        )
        self.config.custom_cta_url = (
            "https://example.com/photography"
        )
        self.config.save(update_fields=[
            "cta_every",
            "enabled_campaigns",
            "custom_cta_title",
            "custom_cta_url",
        ])

        reservation = self.reserve("custom-business")
        reservation.refresh_from_db()

        self.assertEqual(reservation.campaign, "custom")
        self.assertEqual(
            reservation.destination_url,
            "https://example.com/photography",
        )
        self.assertEqual(
            reservation.suffix_translations,
            {
                "en": "Visit my photography shop 📸",
                "es": "Visit my photography shop 📸",
                "pt": "Visit my photography shop 📸",
            },
        )

        self.config.custom_cta_title = "New promotion"
        self.config.custom_cta_url = "https://example.com/new"
        self.config.save(update_fields=[
            "custom_cta_title",
            "custom_cta_url",
        ])

        reservation.refresh_from_db()

        self.assertEqual(
            reservation.destination_url,
            "https://example.com/photography",
        )
        self.assertEqual(
            reservation.suffix_translations["en"],
            "Visit my photography shop 📸",
        )

    def test_valid_out_of_order_reservation(self):
        later = self.reserve(
            "later",
            scheduled_for=self.when + timedelta(hours=72),
        )
        earlier = self.reserve(
            "earlier",
            scheduled_for=self.when,
        )

        self.assertEqual(earlier.sequence_number, 2)
        self.assertLess(earlier.scheduled_for, later.scheduled_for)
        self.assertEqual(AutoPostPublication.objects.count(), 2)

    def test_rejects_collision_with_later_reservation(self):
        self.reserve(
            "later",
            scheduled_for=self.when + timedelta(hours=48),
        )

        with self.assertRaises(ValidationError):
            self.reserve(
                "too-close-before",
                scheduled_for=self.when + timedelta(hours=24),
            )

        self.assertEqual(AutoPostPublication.objects.count(), 1)

    def test_rejects_exact_same_scheduled_time(self):
        self.reserve("first")

        with self.assertRaises(ValidationError):
            self.reserve(
                "same-time",
                scheduled_for=self.when,
            )

        self.config.refresh_from_db()
        self.assertEqual(self.config.next_sequence, 2)
        self.assertEqual(AutoPostPublication.objects.count(), 1)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections
from django.test import TransactionTestCase


class AutoPostConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media_override = override_settings(MEDIA_ROOT=self.temp.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

        self.account = get_user_model().objects.create_user(
            username="autopost_concurrent_creator",
        )
        self.config = AutoPostConfiguration.objects.create(
            account=self.account,
            enabled=True,
            personality="snarky",
            cta_every=3,
            enabled_campaigns=["founder"],
        )

        asset = PlatformMediaAsset(
            account=self.account,
            sha256="c" * 64,
            display_order=0,
        )
        asset.image.save(
            "concurrent.webp",
            ContentFile(b"test-media"),
            save=True,
        )
        self.when = timezone.now() + timedelta(days=3)

    def run_parallel(self, requests):
        barrier = Barrier(2)

        def worker(key, when):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                item = reserve_autopost(
                    account_id=self.account.pk,
                    request_key=key,
                    scheduled_for=when,
                )
                return item.pk, item.sequence_number
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(worker, key, when)
                for key, when in requests
            ]
            return [future.result(timeout=30) for future in futures]

    def test_simultaneous_distinct_requests(self):
        results = self.run_parallel([
            ("concurrent-a", self.when),
            ("concurrent-b", self.when + timedelta(hours=72)),
        ])

        self.assertEqual(
            sorted(sequence for _, sequence in results),
            [1, 2],
        )
        self.assertEqual(AutoPostPublication.objects.count(), 2)

        self.config.refresh_from_db()
        self.assertEqual(self.config.next_sequence, 3)
        self.assertEqual(self.config.next_media_index, 2)

    def test_simultaneous_duplicate_request(self):
        results = self.run_parallel([
            ("same-key", self.when),
            ("same-key", self.when),
        ])

        self.assertEqual(results[0], results[1])
        self.assertEqual(AutoPostPublication.objects.count(), 1)

        self.config.refresh_from_db()
        self.assertEqual(self.config.next_sequence, 2)
        self.assertEqual(self.config.next_media_index, 1)
