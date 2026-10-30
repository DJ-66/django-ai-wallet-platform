"""Creator media selection security and eligibility tests."""

from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from auctions.ai_services.creator_media_import import (
    select_creator_media,
)


class CreatorMediaSelectionTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name) / "packs"
        self.root.mkdir()

        self.pack = self.root / "creator"
        self.pack.mkdir()

        self.creator = {
            "packs": ["creator"],
            "avatar_source": "creator/avatar.jpg",
        }

    def image(self, name):
        path = self.pack / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic-test-image")
        return path

    def select(self, **kwargs):
        return select_creator_media(
            source_root=self.root,
            creator=self.creator,
            already_scheduled=kwargs.pop(
                "already_scheduled", ()
            ),
            **kwargs,
        )

    def test_selects_two_images_by_default(self):
        for name in ("c.jpg", "a.png", "b.webp"):
            self.image(name)

        self.assertEqual(
            self.select(),
            ["creator/a.png", "creator/b.webp"],
        )

    def test_excludes_avatar(self):
        self.image("avatar.jpg")
        self.image("post.jpg")

        self.assertEqual(
            self.select(),
            ["creator/post.jpg"],
        )

    def test_excludes_explicit_directory(self):
        self.image("explicit/private.jpg")
        self.image("safe.jpg")

        self.assertEqual(
            self.select(),
            ["creator/safe.jpg"],
        )

    def test_excludes_scheduled_history(self):
        self.image("one.jpg")
        self.image("two.jpg")

        self.assertEqual(
            self.select(
                already_scheduled={"creator/one.jpg"}
            ),
            ["creator/two.jpg"],
        )

    def test_excludes_imported_history(self):
        self.image("one.jpg")
        self.image("two.jpg")

        self.assertEqual(
            self.select(
                already_imported={"creator/two.jpg"}
            ),
            ["creator/one.jpg"],
        )

    def test_rejects_invalid_limits(self):
        for limit in (0, 31, True, -1):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    self.select(limit=limit)

    def test_rejects_pack_path_traversal(self):
        self.creator["packs"] = ["../outside"]

        with self.assertRaises(
            (ValidationError, FileNotFoundError)
        ):
            self.select()

    def test_rejects_symlinked_pack(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.root / "linked").symlink_to(
            outside, target_is_directory=True
        )

        self.creator["packs"] = ["linked"]

        with self.assertRaises(ValidationError):
            self.select()

    def test_skips_nested_symlink(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "private.jpg").write_bytes(b"private")

        (self.pack / "linked").symlink_to(
            outside, target_is_directory=True
        )
        self.image("safe.jpg")

        self.assertEqual(
            self.select(),
            ["creator/safe.jpg"],
        )

    def test_deterministic_order(self):
        for name in ("z.jpg", "b.jpg", "a.jpg"):
            self.image(name)

        first = self.select()
        second = self.select()

        self.assertEqual(first, second)
        self.assertEqual(
            first,
            ["creator/a.jpg", "creator/b.jpg"],
        )
