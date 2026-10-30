"""Reject unknown FANZ AI preparation markers."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from auctions.models import FeedPost, ScheduledPublication
from auctions.tests_phase14.test_scheduled_publications import write_jpeg


class InvalidPreparedMarkerTests(TestCase):

    def test_unknown_marker_cannot_publish(self):
        user = get_user_model().objects.create_user(
            username="InvalidMarkerTest",
            password="test-only-password",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "creator/image.jpg"
            source = root / relative
            write_jpeg(source)

            publication = ScheduledPublication.objects.create(
                publication_key="ai:invalidmarker:test",
                creator=user,
                source_path=relative,
                title="Invalid marker test",
                content="Original caption\n\n#Fashion #FANZ",
                campaign_key="ai_unknown",
                scheduled_for=timezone.now(),
                status=ScheduledPublication.STATUS_QUEUED,
            )

            with patch.dict(
                "os.environ",
                {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "Unknown AI publication preparation marker",
                ):
                    call_command(
                        "process_scheduled_publications",
                        source_root=str(root),
                        publication_id=publication.pk,
                    )

            publication.refresh_from_db()

            self.assertEqual(
                FeedPost.objects.filter(user=user).count(),
                0,
            )
            self.assertIsNone(publication.feed_post_id)
            self.assertTrue(source.exists())

            print("Unknown marker rejected: PASS")
            print("Feed posts created: 0")
            print("Original source preserved: PASS")
