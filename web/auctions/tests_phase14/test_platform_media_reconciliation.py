"""Read-only platform media reconciliation regression tests."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from auctions.models import PlatformMediaAsset
from auctions.ai_services.platform_media_reconciliation import (
    audit_platform_media,
)


class PlatformMediaReconciliationTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.media_root = Path(self.temp.name)
        self.storage = self.media_root / "platform_media"
        self.storage.mkdir()

        override = override_settings(
            MEDIA_ROOT=str(self.media_root)
        )
        override.enable()
        self.addCleanup(override.disable)

        self.user = get_user_model().objects.create_user(
            username="reconciliation_creator"
        )

        self.now = datetime(2026, 10, 27, tzinfo=timezone.utc)

    def stored_file(self, name, *, days_old=10):
        path = self.storage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic-webp")

        timestamp = (
            self.now - timedelta(days=days_old)
        ).timestamp()

        os.utime(path, (timestamp, timestamp))
        return path

    def reference(self, relative):
        return PlatformMediaAsset.objects.create(
            account=self.user,
            image=relative,
            sha256="a" * 64,
        )

    def audit(self, **kwargs):
        return audit_platform_media(
            now=self.now,
            **kwargs,
        )

    def test_referenced_file_not_orphan(self):
        self.stored_file("1/valid.webp")
        self.reference("platform_media/1/valid.webp")

        result = self.audit()

        self.assertEqual(result["unreferenced_count"], 0)
        self.assertEqual(result["missing_count"], 0)

    def test_missing_referenced_file_reported(self):
        self.reference("platform_media/1/missing.webp")

        result = self.audit()

        self.assertEqual(result["missing_count"], 1)

    def test_old_orphan_is_candidate(self):
        self.stored_file("1/orphan.webp", days_old=10)

        result = self.audit()

        self.assertEqual(result["unreferenced_count"], 1)
        self.assertEqual(result["retention_eligible_count"], 1)

    def test_recent_orphan_not_candidate(self):
        self.stored_file("1/recent.webp", days_old=1)

        result = self.audit()

        self.assertEqual(result["unreferenced_count"], 1)
        self.assertEqual(result["retention_eligible_count"], 0)

    def test_retention_below_seven_rejected(self):
        with self.assertRaises(ValueError):
            self.audit(retention_days=6)

    def test_symlinked_file_reported(self):
        outside = self.media_root / "outside.webp"
        outside.write_bytes(b"outside")

        (self.storage / "linked.webp").symlink_to(outside)

        result = self.audit()

        self.assertEqual(result["symlink_count"], 1)
        self.assertEqual(result["retention_eligible_count"], 0)

    def test_nested_symlink_directory_reported(self):
        outside = self.media_root / "outside"
        outside.mkdir()
        (outside / "private.webp").write_bytes(b"private")

        nested = self.storage / "1"
        nested.mkdir()
        (nested / "linked").symlink_to(
            outside,
            target_is_directory=True,
        )

        result = self.audit()

        self.assertEqual(result["symlink_count"], 1)
        self.assertEqual(result["retention_eligible_count"], 0)
        self.assertEqual(result["unreferenced_count"], 0)

    def test_symlinked_storage_root_rejected(self):
        outside = self.media_root / "outside"
        outside.mkdir()

        self.storage.rmdir()
        self.storage.symlink_to(
            outside,
            target_is_directory=True,
        )

        with self.assertRaises(ValueError):
            self.audit()
