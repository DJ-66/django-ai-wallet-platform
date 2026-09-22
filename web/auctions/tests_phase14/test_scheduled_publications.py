import json
import tempfile
from io import BytesIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from PIL import Image

from auctions.models import FeedPost, ScheduledPublication
from auctions.management.commands import process_scheduled_publications


User = get_user_model()


def write_jpeg(path):
    output = BytesIO()

    Image.new(
        "RGB",
        (640, 800),
        (120, 140, 160),
    ).save(
        output,
        format="JPEG",
        quality=90,
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_bytes(output.getvalue())


class ScheduledPublicationCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="workercreator",
            password="test-password",
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.source_root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_due_publication_publishes_and_consumes_source(self):
        relative_path = "Worker Pack/image.jpg"
        source = self.source_root / relative_path
        write_jpeg(source)

        publication = ScheduledPublication.objects.create(
            publication_key="worker-success-1",
            creator=self.user,
            source_path=relative_path,
            title="Worker title",
            content="Worker content",
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        call_command(
            "process_scheduled_publications",
            source_root=str(self.source_root),
        )

        publication.refresh_from_db()

        self.assertEqual(
            publication.status,
            ScheduledPublication.STATUS_PUBLISHED,
        )
        self.assertEqual(publication.attempt_count, 1)
        self.assertIsNotNone(publication.feed_post_id)
        self.assertIsNotNone(publication.published_at)
        self.assertEqual(publication.last_error, "")

        post = publication.feed_post

        self.assertEqual(post.user, self.user)
        self.assertEqual(post.title, "Worker title")
        self.assertEqual(post.content, "Worker content")

        media = post.media.get()

        self.assertTrue(media.file.name.endswith(".webp"))
        self.assertTrue(
            media.file.storage.exists(media.file.name)
        )

        self.assertFalse(source.exists())

    def test_missing_source_marks_publication_failed(self):
        publication = ScheduledPublication.objects.create(
            publication_key="worker-missing-1",
            creator=self.user,
            source_path="Missing Pack/missing.jpg",
            content="Missing source",
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        with self.assertRaises(Exception):
            call_command(
                "process_scheduled_publications",
                source_root=str(self.source_root),
            )

        publication.refresh_from_db()

        self.assertEqual(
            publication.status,
            ScheduledPublication.STATUS_FAILED,
        )
        self.assertEqual(publication.attempt_count, 1)
        self.assertIn(
            "does not exist",
            publication.last_error,
        )

        self.assertEqual(
            FeedPost.objects.filter(user=self.user).count(),
            0,
        )

    def test_reserved_avatar_source_is_refused(self):
        relative_path = "Reserved Pack/avatar.jpg"
        source = self.source_root / relative_path
        write_jpeg(source)

        publication = ScheduledPublication.objects.create(
            publication_key="worker-reserved-1",
            creator=self.user,
            source_path=relative_path,
            content="Must not publish",
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        original_manifest_path = (
            process_scheduled_publications.MANIFEST_PATH
        )

        manifest = self.source_root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "creators": [
                        {
                            "account": "workercreator",
                            "avatar_source": relative_path,
                        }
                    ]
                }
            )
        )

        process_scheduled_publications.MANIFEST_PATH = manifest

        try:
            with self.assertRaises(Exception):
                call_command(
                    "process_scheduled_publications",
                    source_root=str(self.source_root),
                )
        finally:
            process_scheduled_publications.MANIFEST_PATH = (
                original_manifest_path
            )

        publication.refresh_from_db()

        self.assertEqual(
            publication.status,
            ScheduledPublication.STATUS_FAILED,
        )
        self.assertEqual(publication.attempt_count, 1)
        self.assertIn(
            "reserved",
            publication.last_error.lower(),
        )

        self.assertTrue(source.exists())

        self.assertEqual(
            FeedPost.objects.filter(user=self.user).count(),
            0,
        )

    def test_future_publication_is_not_claimed(self):
        from datetime import timedelta

        publication = ScheduledPublication.objects.create(
            publication_key="worker-future-1",
            creator=self.user,
            source_path="Future Pack/image.jpg",
            content="Not due",
            scheduled_for=timezone.now() + timedelta(hours=1),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        call_command(
            "process_scheduled_publications",
            source_root=str(self.source_root),
        )

        publication.refresh_from_db()

        self.assertEqual(
            publication.status,
            ScheduledPublication.STATUS_QUEUED,
        )
        self.assertEqual(publication.attempt_count, 0)
        self.assertIsNone(publication.feed_post_id)

    def test_publication_id_can_claim_future_publication(self):
        from datetime import timedelta

        relative_path = "Forced Publication/image.jpg"
        source = self.source_root / relative_path
        write_jpeg(source)

        publication = ScheduledPublication.objects.create(
            publication_key="worker-forced-future-1",
            creator=self.user,
            source_path=relative_path,
            title="Forced title",
            content="Forced content",
            scheduled_for=timezone.now() + timedelta(hours=6),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        call_command(
            "process_scheduled_publications",
            source_root=str(self.source_root),
            publication_id=publication.id,
        )

        publication.refresh_from_db()

        self.assertEqual(
            publication.status,
            ScheduledPublication.STATUS_PUBLISHED,
        )
        self.assertEqual(publication.attempt_count, 1)
        self.assertIsNotNone(publication.feed_post_id)
        self.assertIsNotNone(publication.published_at)
        self.assertFalse(source.exists())

    def test_dry_run_leaves_publication_queued(self):
        relative_path = "Dry Run/image.jpg"
        source = self.source_root / relative_path
        write_jpeg(source)

        publication = ScheduledPublication.objects.create(
            publication_key="worker-dry-run-1",
            creator=self.user,
            source_path=relative_path,
            content="Dry run",
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        call_command(
            "process_scheduled_publications",
            source_root=str(self.source_root),
            dry_run=True,
        )

        publication.refresh_from_db()

        self.assertEqual(
            publication.status,
            ScheduledPublication.STATUS_QUEUED,
        )
        self.assertEqual(publication.attempt_count, 0)
        self.assertIsNone(publication.feed_post_id)
        self.assertTrue(source.exists())
