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

from auctions.ai_services.creator_copy import CreatorCopyError
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
                            "post_style": {
                                "hashtags": [
                                    "CreatorA",
                                    "Lifestyle",
                                    "Style",
                                    "AIInfluencer",
                                    "DigitalCreator",
                                    "CreatorLife",
                                ],
                            },
                        },
                        {
                            "account": "CreatorB",
                            "packs": ["PackB"],
                            "avatar_source": None,
                            "post_style": {
                                "hashtags": [
                                    "CreatorB",
                                    "Lifestyle",
                                    "Fashion",
                                    "AIInfluencer",
                                    "DigitalCreator",
                                    "CreatorLife",
                                ],
                            },
                        },
                        {
                            "account": "CreatorC",
                            "packs": ["PackC"],
                            "avatar_source": None,
                            "post_style": {
                                "hashtags": [
                                    "CreatorC",
                                    "Lifestyle",
                                    "Creative",
                                    "AIInfluencer",
                                    "DigitalCreator",
                                    "CreatorLife",
                                ],
                            },
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

        # Explicit content must never enter the public auto-post pool.
        write_image(
            self.root / "PackA" / "explicit" / "private.jpg"
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

    def run_generator(
        self,
        *,
        vision_result=None,
        vision_error=None,
        **kwargs,
    ):
        kwargs.setdefault("seed", 14)

        if vision_result is None:
            vision_result = {
                "title": "Vision Test Title",
                "caption": "Vision test caption.",
                "hashtags": [
                    "Lifestyle",
                    "Style",
                    "DigitalCreator",
                    "CreatorLife",
                ],
            }

        with (
            patch.object(
                generate_ai_publications,
                "MANIFEST_PATH",
                self.manifest,
            ),
            patch.object(
                generate_ai_publications,
                "generate_creator_post_copy",
            ) as generate_copy,
            patch.object(
                generate_ai_publications.settings,
                "CREATOR_VISION_COPY_ENABLED",
                True,
            ),
        ):
            if vision_error is not None:
                generate_copy.side_effect = vision_error
            else:
                generate_copy.return_value = vision_result

            call_command(
                "generate_ai_publications",
                source_root=str(self.root),
                **kwargs,
            )

            return generate_copy

    def test_vision_copy_is_used_when_generation_succeeds(self):
        vision_result = {
            "title": "Palm Tree Shadows",
            "caption": "Boardwalk lines beneath the palms.",
            "hashtags": [
                "Lifestyle",
                "Style",
                "DigitalCreator",
                "CreatorLife",
            ],
        }

        generate_copy = self.run_generator(
            vision_result=vision_result,
        )

        self.assertEqual(generate_copy.call_count, 3)

        publication = (
            ScheduledPublication.objects
            .filter(creator=self.users[0])
            .get()
        )

        self.assertEqual(
            publication.title,
            "Palm Tree Shadows",
        )

        self.assertIn(
            "Boardwalk lines beneath the palms.",
            publication.content,
        )

        hashtags = [
            token
            for token in publication.content.split()
            if token.startswith("#")
        ]

        self.assertEqual(len(hashtags), 6)
        self.assertIn("#AIInfluencer", hashtags)
        self.assertIn("#FANZ", hashtags)

    def test_vision_failure_falls_back_to_template_copy(self):
        generate_copy = self.run_generator(
            vision_error=CreatorCopyError(
                "test vision failure"
            ),
        )

        self.assertEqual(generate_copy.call_count, 3)

        publications = ScheduledPublication.objects.all()

        self.assertEqual(publications.count(), 3)

        for publication in publications:
            self.assertIn(
                publication.title,
                generate_ai_publications.TITLES,
            )

            self.assertTrue(
                any(
                    caption in publication.content
                    for caption
                    in generate_ai_publications.CAPTIONS
                )
            )

            hashtags = [
                token
                for token in publication.content.split()
                if token.startswith("#")
            ]

            self.assertEqual(len(hashtags), 6)
            self.assertIn("#FANZ", hashtags)

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

    def test_published_creator_gets_next_slot_24_hours_later(self):
        self.run_generator(seed=14)

        creator_a = self.users[0]

        first = (
            ScheduledPublication.objects
            .filter(creator=creator_a)
            .get()
        )

        first_scheduled_for = first.scheduled_for

        # Make only CreatorA due, then use the real publication
        # worker so the published-state DB constraint is satisfied.
        first.scheduled_for = timezone.now() - timedelta(minutes=1)
        first.save(
            update_fields=["scheduled_for"]
        )

        call_command(
            "process_scheduled_publications",
            source_root=str(self.root),
            publication_id=first.id,
        )

        first.refresh_from_db()

        self.assertEqual(
            first.status,
            ScheduledPublication.STATUS_PUBLISHED,
        )
        self.assertIsNotNone(first.feed_post_id)

        # Restore the original slot as the scheduling anchor.
        first.scheduled_for = first_scheduled_for
        first.save(
            update_fields=["scheduled_for"]
        )

        self.run_generator(seed=15)

        rows = list(
            ScheduledPublication.objects
            .filter(creator=creator_a)
            .order_by("scheduled_for")
        )

        self.assertEqual(len(rows), 2)

        self.assertEqual(
            rows[1].scheduled_for,
            first_scheduled_for + timedelta(hours=24),
        )

        # CreatorB and CreatorC still had pending rows,
        # so they must not receive another one.
        for creator in self.users[1:]:
            self.assertEqual(
                ScheduledPublication.objects.filter(
                    creator=creator
                ).count(),
                1,
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

    def test_generated_posts_have_title_and_six_hashtags(self):
        self.run_generator()

        for publication in ScheduledPublication.objects.all():
            self.assertTrue(publication.title.strip())

            hashtags = [
                token
                for token in publication.content.split()
                if token.startswith("#")
            ]

            self.assertEqual(
                len(hashtags),
                6,
            )
            self.assertIn(
                "#FANZ",
                hashtags,
            )

    def test_explicit_directory_is_never_queued(self):
        # Run twice so CreatorA consumes both eligible public images.
        # If explicit filtering regresses, private.jpg could enter the queue.
        self.run_generator(seed=14)
        self.run_generator(seed=15)

        sources = set(
            ScheduledPublication.objects.values_list(
                "source_path",
                flat=True,
            )
        )

        self.assertNotIn(
            "PackA/explicit/private.jpg",
            sources,
        )

        self.assertFalse(
            any(
                "/explicit/" in source.lower()
                for source in sources
            )
        )

    def test_generator_keeps_only_one_pending_per_creator(self):
        self.run_generator(seed=14)

        self.assertEqual(
            ScheduledPublication.objects.filter(
                status=ScheduledPublication.STATUS_QUEUED,
            ).count(),
            3,
        )

        # Re-running while all creators have pending work
        # must not stack additional future rows.
        self.run_generator(seed=15)

        self.assertEqual(
            ScheduledPublication.objects.count(),
            3,
        )

        for creator in self.users:
            self.assertEqual(
                ScheduledPublication.objects.filter(
                    creator=creator,
                    status=ScheduledPublication.STATUS_QUEUED,
                ).count(),
                1,
            )

    def test_dry_run_creates_nothing(self):
        self.run_generator(dry_run=True)

        self.assertEqual(
            ScheduledPublication.objects.count(),
            0,
        )
