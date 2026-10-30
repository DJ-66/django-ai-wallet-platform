"""Rollback safety for scheduled AI publishing."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from auctions.models import FeedPost, ScheduledPublication
from auctions.tests_phase14.test_scheduled_publications import write_jpeg


class LegacySuffixRollbackTests(TransactionTestCase):

    def test_finalization_failure_rolls_back_post_and_media(self):
        user = get_user_model().objects.create_user(
            username="SuffixRollbackTest",
            password="test-only-password",
        )

        with tempfile.TemporaryDirectory() as directory:
            media_root = str(Path(directory) / "media")
            root = Path(directory)
            source = root / "creator/image.jpg"
            write_jpeg(source)

            with override_settings(MEDIA_ROOT=media_root):
                publication = ScheduledPublication.objects.create(
                    publication_key="ai:rollback:test-1",
                    creator=user,
                    source_path="creator/image.jpg",
                    title="Rollback test",
                    content="Original caption.\n\n#Fashion #FANZ",
                    scheduled_for=timezone.now(),
                    status=ScheduledPublication.STATUS_QUEUED,
                )

                from auctions.models import FeedPostMedia

                original_save = ScheduledPublication.save

                def fail_finalization(instance, *args, **kwargs):
                    if instance.status == ScheduledPublication.STATUS_PUBLISHED:
                        raise RuntimeError("Injected finalization failure")
                    return original_save(instance, *args, **kwargs)

                with (
                    patch.dict(
                        "os.environ",
                        {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
                    ),
                    patch.object(
                        ScheduledPublication,
                        "save",
                        fail_finalization,
                    ),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "Injected finalization failure",
                    ):
                        call_command(
                            "process_scheduled_publications",
                            source_root=str(root),
                            publication_id=publication.pk,
                        )

            publication.refresh_from_db()

            self.assertEqual(
                publication.status,
                ScheduledPublication.STATUS_FAILED,
            )
            self.assertIsNone(publication.feed_post_id)
            self.assertEqual(
                FeedPost.objects.filter(user=user).count(),
                0,
            )
            self.assertEqual(
                FeedPostMedia.objects.filter(post__user=user).count(),
                0,
            )
            self.assertTrue(source.exists())

            # Verify only media belonging to this test.
            media_dir = Path(media_root)
            self.assertFalse(
                any(p.is_file() for p in media_dir.rglob("*")),
                "Rollback left uploaded media behind",
            )
