import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from PIL import Image

from auctions.models import ScheduledPublication
from auctions.management.commands import generate_ai_publications


User = get_user_model()


def write_image(path):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    Image.new(
        "RGB",
        (200, 300),
        (120, 140, 160),
    ).save(
        path,
        format="JPEG",
    )


class GenerateAIPublicationsTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

        self.users = []

        for name in ["CreatorA", "CreatorB", "CreatorC"]:
            self.users.append(
                User.objects.create_user(
                    username=name,
                    password="test-password",
                )
            )

        self.manifest = self.root / "manifest.json"

        self.manifest.write_text(
            json.dumps(
                {
                    "creators": [
                        {
                            "account": "CreatorA",
                            "packs": ["PackA"],
                            "avatar_source": (
                                "PackA/avatar.jpg"
                            ),
                        },
                        {
                            "account": "CreatorB",
                            "packs": ["PackB"],
                            "avatar_source": None,
                        },
                        {
                            "account": "CreatorC",
                            "packs": ["PackC"],
                            "avatar_source": None,
                        },
                    ]
                }
            )
        )

        write_image(
            self.root / "PackA" / "avatar.jpg"
        )
        write_image(
            self.root / "PackA" / "post-1.jpg"
        )
        write_image(
            self.root / "PackA" / "post-2.jpg"
        )

        for pack in ["PackB", "PackC"]:
            write_image(
                self.root / pack / "post-1.jpg"
            )
            write_image(
                self.root / pack / "post-2.jpg"
            )

    def tearDown(self):
        self.tempdir.cleanup()

    def run_generator(self, **kwargs):
        kwargs.setdefault("seed", 14)

        with patch.object(
            generate_ai_publications,
            "MANIFEST_PATH",
            self.manifest,
        ):
            call_command(
                "generate_ai_publications",
                source_root=str(self.root),
                **kwargs,
            )

    def test_initial_queue_staggers_creators_over_24_hours(self):
        before = timezone.now()

        self.run_generator()

        rows = list(
            ScheduledPublication.objects
            .order_by("scheduled_for")
        )

        self.assertEqual(len(rows), 3)

        spacing_one = (
            rows[1].scheduled_for
            - rows[0].scheduled_for
        )
        spacing_two = (
            rows[2].scheduled_for
            - rows[1].scheduled_for
        )

        self.assertAlmostEqual(
            spacing_one.total_seconds(),
            8 * 3600,
            delta=2,
        )
        self.assertAlmostEqual(
            spacing_two.total_seconds(),
            8 * 3600,
            delta=2,
        )

        self.assertGreaterEqual(
            rows[0].scheduled_for,
            before,
        )

    def test_second_run_extends_each_creator_by_24_hours(self):
        self.run_generator()

        first_rows = {
            row.creator.username: row.scheduled_for
            for row in ScheduledPublication.objects.all()
        }

        self.run_generator(seed=15)

        self.assertEqual(
            ScheduledPublication.objects.count(),
            6,
        )

        for user in self.users:
            rows = list(
                ScheduledPublication.objects
                .filter(creator=user)
                .order_by("scheduled_for")
            )

            self.assertEqual(len(rows), 2)

            self.assertEqual(
                rows[1].scheduled_for,
                rows[0].scheduled_for
                + timedelta(hours=24),
            )

    def test_avatar_source_is_never_queued(self):
        self.run_generator()

        sources = set(
            ScheduledPublication.objects.values_list(
                "source_path",
                flat=True,
            )
        )

        self.assertNotIn(
            "PackA/avatar.jpg",
            sources,
        )

    def test_initial_queue_honors_start_delay(self):
        before = timezone.now()

        self.run_generator(
            start_delay_minutes=60,
        )

        first = (
            ScheduledPublication.objects
            .order_by("scheduled_for")
            .first()
        )

        delay = first.scheduled_for - before

        self.assertGreaterEqual(
            delay.total_seconds(),
            59 * 60,
        )
        self.assertLess(
            delay.total_seconds(),
            61 * 60,
        )

    def test_dry_run_creates_nothing(self):
        self.run_generator(dry_run=True)

        self.assertEqual(
            ScheduledPublication.objects.count(),
            0,
        )
