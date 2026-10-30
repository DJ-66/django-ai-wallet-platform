"""Bounded creator media persistence regression tests."""

import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from PIL import Image

from auctions.ai_services.creator_media_persistence import (
    import_creator_media,
)
from auctions.models import PlatformMediaAsset, ScheduledPublication


class CreatorMediaPersistenceTests(TransactionTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        root = Path(self.temp.name)
        self.packs = root / "packs"
        self.packs.mkdir()
        self.pack = self.packs / "creator"
        self.pack.mkdir()

        self.media = root / "media"
        self.media.mkdir()

        media_override = override_settings(MEDIA_ROOT=str(self.media))
        media_override.enable()
        self.addCleanup(media_override.disable)

        self.user = get_user_model().objects.create_user(
            username="test_import_creator",
        )

        self.manifest = root / "manifest.json"
        self.manifest.write_text(json.dumps({
            "creators": [{
                "account": self.user.username,
                "packs": ["creator"],
                "avatar_source": "creator/avatar.jpg",
            }]
        }))

        manifest_patch = patch(
            "auctions.ai_services.creator_media_persistence.MANIFEST_PATH",
            self.manifest,
        )
        manifest_patch.start()
        self.addCleanup(manifest_patch.stop)

    def image(self, name="photo.jpg"):
        output = BytesIO()
        Image.new("RGB", (400, 300), (120, 80, 160)).save(
            output, format="JPEG"
        )
        path = self.pack / name
        path.write_bytes(output.getvalue())
        return path

    def run_import(self, paths):
        return import_creator_media(
            account=self.user,
            source_root=self.packs,
            relative_paths=paths,
        )

    def test_successful_webp_registration(self):
        source = self.image()
        result = self.run_import(["creator/photo.jpg"])

        self.assertEqual(result["created"], 1)
        self.assertTrue(source.exists())

        asset = PlatformMediaAsset.objects.get(account=self.user)
        self.assertTrue(asset.image.name.endswith(".webp"))
        self.assertTrue(asset.image.storage.exists(asset.image.name))

    def test_duplicate_import_skipped(self):
        self.image()
        self.run_import(["creator/photo.jpg"])

        result = self.run_import(["creator/photo.jpg"])

        self.assertEqual(result["duplicates"], 1)
        self.assertEqual(
            PlatformMediaAsset.objects.filter(account=self.user).count(),
            1,
        )

    def test_unauthorized_account_rejected(self):
        self.image()
        other = get_user_model().objects.create_user(
            username="unauthorized_import_user",
        )

        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            import_creator_media(
                account=other,
                source_root=self.packs,
                relative_paths=["creator/photo.jpg"],
            )

    def test_scheduled_image_rejected(self):
        self.image()

        ScheduledPublication.objects.create(
            creator=self.user,
            publication_key="test-import-history",
            source_path="creator/photo.jpg",
            scheduled_for=__import__(
                "django.utils.timezone", fromlist=["now"]
            ).now(),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        result = self.run_import(["creator/photo.jpg"])

        self.assertEqual(result["rejected"], 1)
        self.assertFalse(
            PlatformMediaAsset.objects.filter(account=self.user).exists()
        )

    def test_invalid_image_rejected(self):
        path = self.pack / "invalid.jpg"
        path.write_bytes(b"not-an-image")

        result = self.run_import(["creator/invalid.jpg"])

        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["created"], 0)

    def test_symlinked_file_rejected(self):
        outside = Path(self.temp.name) / "outside.jpg"
        outside.write_bytes(b"private")

        (self.pack / "linked.jpg").symlink_to(outside)

        result = self.run_import(["creator/linked.jpg"])

        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["created"], 0)

    def test_symlinked_directory_rejected(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "photo.jpg").write_bytes(b"private")

        (self.pack / "linked").symlink_to(
            outside,
            target_is_directory=True,
        )

        result = self.run_import(["creator/linked/photo.jpg"])

        self.assertEqual(result["rejected"], 1)

    def test_oversized_file_rejected(self):
        path = self.pack / "large.jpg"

        with path.open("wb") as stream:
            stream.truncate(40 * 1024 * 1024 + 1)

        result = self.run_import(["creator/large.jpg"])

        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["created"], 0)

    def test_unapproved_pack_rejected(self):
        other = self.packs / "unapproved"
        other.mkdir()

        output = BytesIO()
        Image.new("RGB", (100, 100)).save(
            output, format="JPEG"
        )

        (other / "photo.jpg").write_bytes(output.getvalue())

        result = self.run_import(["unapproved/photo.jpg"])

        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["created"], 0)

    def test_storage_failure_preserves_source(self):
        source = self.image()

        with patch(
            "auctions.ai_services.creator_media_persistence.save_platform_media",
            side_effect=RuntimeError("synthetic storage failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.run_import(["creator/photo.jpg"])

        self.assertTrue(source.exists())
        self.assertEqual(
            PlatformMediaAsset.objects.filter(
                account=self.user
            ).count(),
            0,
        )

    def test_database_failure_removes_written_webp(self):
        source = self.image("rollback.jpg")

        from auctions.models import PlatformMediaAsset

        def fail_after_file_write(instance, *args, **kwargs):
            assert instance.image.name
            assert instance.image.storage.exists(
                instance.image.name
            )
            raise RuntimeError("synthetic database insert failure")

        with patch.object(
            PlatformMediaAsset,
            "save",
            new=fail_after_file_write,
        ):
            with self.assertRaises(RuntimeError):
                self.run_import(["creator/rollback.jpg"])

        self.assertTrue(source.exists())

        self.assertEqual(
            list(self.media.rglob("*.webp")),
            [],
        )

        self.assertFalse(
            PlatformMediaAsset.objects.filter(
                account=self.user
            ).exists()
        )

    def test_outer_transaction_rejected(self):
        from django.db import transaction

        source = self.image("atomic.jpg")

        with transaction.atomic():
            with self.assertRaisesRegex(
                RuntimeError,
                "requires an autocommit context",
            ):
                self.run_import(["creator/atomic.jpg"])

        self.assertTrue(source.exists())
        self.assertFalse(
            PlatformMediaAsset.objects.filter(
                account=self.user
            ).exists()
        )

    def test_unapproved_nested_pack_rejected(self):
        outside = self.packs / "another_creator"
        outside.mkdir()

        nested = outside / "nested"
        nested.mkdir()

        output = BytesIO()
        Image.new("RGB", (100, 100)).save(
            output,
            format="JPEG",
        )

        (nested / "photo.jpg").write_bytes(output.getvalue())

        result = self.run_import([
            "another_creator/nested/photo.jpg"
        ])

        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["created"], 0)

    def test_approved_pack_symlink_replacement_rejected(self):
        source = self.image("replacement.jpg")

        outside = Path(self.temp.name) / "outside"
        outside.mkdir()

        (outside / "replacement.jpg").write_bytes(
            source.read_bytes()
        )

        original_read = (
            __import__(
                "auctions.ai_services.creator_media_persistence",
                fromlist=["read_creator_media"],
            ).read_creator_media
        )

        def replace_before_read(*, source_root, relative_path):
            self.pack.rename(self.packs / "creator_original")

            (self.packs / "creator").symlink_to(
                outside,
                target_is_directory=True,
            )

            return original_read(
                source_root=source_root,
                relative_path=relative_path,
            )

        with patch(
            "auctions.ai_services.creator_media_persistence.read_creator_media",
            side_effect=replace_before_read,
        ):
            result = self.run_import([
                "creator/replacement.jpg"
            ])

        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["created"], 0)
        self.assertFalse(
            PlatformMediaAsset.objects.filter(
                account=self.user
            ).exists()
        )
