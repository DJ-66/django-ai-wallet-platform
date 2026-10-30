"""Secure creator-media filesystem regression tests."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from auctions.ai_services.secure_creator_media import (
    MAX_SOURCE_BYTES,
    read_creator_media,
)


class SecureCreatorMediaTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.base = Path(self.temp.name)
        self.root = self.base / "packs"
        self.root.mkdir()

        self.pack = self.root / "creator"
        self.pack.mkdir()

    def read(self, relative):
        return read_creator_media(
            source_root=self.root,
            relative_path=relative,
        )

    def test_regular_file_read(self):
        (self.pack / "photo.jpg").write_bytes(b"safe-image")

        self.assertEqual(
            self.read("creator/photo.jpg"),
            b"safe-image",
        )

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValidationError):
            self.read("../outside.jpg")

    def test_absolute_path_rejected(self):
        with self.assertRaises(ValidationError):
            self.read("/etc/passwd")

    def test_symlinked_file_rejected(self):
        outside = self.base / "outside.jpg"
        outside.write_bytes(b"private")

        (self.pack / "linked.jpg").symlink_to(outside)

        with self.assertRaises(ValidationError):
            self.read("creator/linked.jpg")

    def test_symlinked_directory_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "private.jpg").write_bytes(b"private")

        (self.pack / "linked").symlink_to(
            outside,
            target_is_directory=True,
        )

        with self.assertRaises(ValidationError):
            self.read("creator/linked/private.jpg")

    def test_missing_file_rejected(self):
        with self.assertRaises(ValidationError):
            self.read("creator/missing.jpg")

    def test_oversized_file_rejected(self):
        path = self.pack / "large.jpg"

        with path.open("wb") as stream:
            stream.truncate(MAX_SOURCE_BYTES + 1)

        with self.assertRaises(ValidationError):
            self.read("creator/large.jpg")

    def test_source_file_preserved(self):
        path = self.pack / "photo.jpg"
        path.write_bytes(b"original")

        self.read("creator/photo.jpg")

        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), b"original")

    def test_invalid_path_type_rejected(self):
        with self.assertRaises(ValidationError):
            self.read(None)

    def test_directory_as_file_rejected(self):
        with self.assertRaises(ValidationError):
            self.read("creator")
