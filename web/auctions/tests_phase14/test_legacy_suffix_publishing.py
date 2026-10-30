"""End-to-end publishing test for FANZ AI creator suffixes."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from auctions.ai_services.legacy_creator_suffix import (
    suffix_for_publication,
)
from auctions.models import ScheduledPublication
from auctions.ai_services.legacy_suffix_detection import (
    is_decorated_ai_publication,
)
from auctions.tests_phase14.test_scheduled_publications import (
    write_jpeg,
)


class LegacySuffixPublishingTests(TestCase):

    def test_ai_publication_contains_approved_suffix(self):
        user = get_user_model().objects.create_user(
            username="SuffixPublisherTest",
            password="test-only-password",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "creator/image.jpg"
            write_jpeg(root / relative)

            publication = ScheduledPublication.objects.create(
                publication_key="ai:suffixpublisher:test-1",
                creator=user,
                source_path=relative,
                title="Creator title",
                content=(
                    "Original creator caption."
                    "\n\n#Fashion #FANZ"
                ),
                scheduled_for=timezone.now(),
                campaign_key="ai_legacy_suffix",
                status=ScheduledPublication.STATUS_QUEUED,
            )

            with patch.dict(
                "os.environ",
                {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
            ):
                call_command(
                    "process_scheduled_publications",
                    source_root=str(root),
                )

            publication.refresh_from_db()
            self.assertTrue(
                is_decorated_ai_publication(publication)
            )

            self.assertEqual(
                publication.status,
                ScheduledPublication.STATUS_PUBLISHED,
            )

            post = publication.feed_post
            self.assertIsNotNone(post)

            suffix, destination = suffix_for_publication(
                username=user.username,
                publication_key=publication.publication_key,
                sequence=1,
            )

            self.assertIsNone(destination)
            self.assertIn(
                suffix.translations["en"],
                post.content,
            )
            self.assertTrue(
                post.content.endswith("#Fashion #FANZ")
            )
            self.assertEqual(
                post.content.count(suffix.translations["en"]),
                1,
            )
            self.assertFalse((root / relative).exists())

            print("Published suffix: PASS")
            print("Hashtags preserved: PASS")
            print("Suffix duplication: NONE")

    def test_fourth_ai_publication_contains_founder_cta(self):
        from datetime import timedelta

        user = get_user_model().objects.create_user(
            username="FounderCTATest",
            password="test-only-password",
        )

        now = timezone.now()

        # Historical records establish sequence 1 and 2.
        for number in (1, 2, 3):
            ScheduledPublication.objects.create(
                publication_key=f"ai:foundercta:history-{number}",
                creator=user,
                source_path=f"historical/image-{number}.jpg",
                title="Historical title",
                content="Historical caption\n\n#Fashion #FANZ",
                scheduled_for=now - timedelta(days=3 - number),
                status=ScheduledPublication.STATUS_QUEUED,
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "creator/third.jpg"
            write_jpeg(root / relative)

            publication = ScheduledPublication.objects.create(
                publication_key="ai:foundercta:fourth",
                creator=user,
                source_path=relative,
                title="Third publication",
                content="Third caption\n\n#Fashion #FANZ",
                scheduled_for=now,
                campaign_key="ai_legacy_suffix",
                status=ScheduledPublication.STATUS_QUEUED,
            )

            with patch.dict(
                "os.environ",
                {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
            ):
                call_command(
                    "process_scheduled_publications",
                    source_root=str(root),
                    publication_id=publication.pk,
                )

            publication.refresh_from_db()
            self.assertTrue(
                is_decorated_ai_publication(publication)
            )

            self.assertEqual(
                publication.status,
                ScheduledPublication.STATUS_PUBLISHED,
            )

            suffix, destination = suffix_for_publication(
                username=user.username,
                publication_key=publication.publication_key,
                sequence=4,
            )

            self.assertEqual(suffix.campaign, "founder")
            self.assertIsNotNone(destination)

            content = publication.feed_post.content

            self.assertEqual(
                content.count(suffix.translations["en"]),
                1,
            )
            self.assertIn(destination.url, content)
            self.assertTrue(
                content.endswith("#Fashion #FANZ")
            )

            print("Founder CTA publication: PASS")
            print("Approved destination: PASS")


    def test_prepared_gemma_caption_publishes_without_duplication(self):
        user = get_user_model().objects.create_user(
            username="PreparedGemmaTest",
            password="test-only-password",
        )

        closer = "Tell me your most ridiculous story in my DMs."
        prepared = (
            "I had a plan. Then chaos happened.\n"
            + closer
            + "\n\n#Fashion #FANZ"
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "creator/prepared.jpg"
            write_jpeg(root / relative)

            publication = ScheduledPublication.objects.create(
                publication_key="ai:preparedgemma:test",
                creator=user,
                source_path=relative,
                title="Prepared Gemma post",
                content=prepared,
                campaign_key="ai_gemma4",
                scheduled_for=timezone.now(),
                status=ScheduledPublication.STATUS_QUEUED,
            )

            with patch.dict(
                "os.environ",
                {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
            ):
                call_command(
                    "process_scheduled_publications",
                    source_root=str(root),
                    publication_id=publication.pk,
                )

            publication.refresh_from_db()

            self.assertEqual(
                publication.status,
                ScheduledPublication.STATUS_PUBLISHED,
            )
            self.assertEqual(
                publication.feed_post.content,
                prepared,
            )
            self.assertEqual(
                publication.feed_post.content.count(closer),
                1,
            )
            self.assertFalse((root / relative).exists())

            print("Prepared Gemma caption: PASS")
            print("Duplicate ending: NONE")


class UnmarkedLegacyQueueCompatibilityTests(TestCase):
    """Protect Recovery v2 publications during Gemma 4 rollout."""

    def test_unmarked_ai_caption_publishes_unchanged(self):
        user = get_user_model().objects.create_user(
            username="UnmarkedLegacyQueueTest",
            password="test-only-password",
        )

        original = (
            "An ordinary creator caption, exactly as scheduled."
            "\n\n#Fashion #FANZ"
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "creator/legacy.jpg"
            write_jpeg(root / relative)

            publication = ScheduledPublication.objects.create(
                publication_key="ai:legacyqueue:unmarked",
                creator=user,
                source_path=relative,
                title="Original legacy title",
                content=original,
                campaign_key="",
                scheduled_for=timezone.now(),
                status=ScheduledPublication.STATUS_QUEUED,
            )

            with patch.dict(
                "os.environ",
                {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
            ):
                call_command(
                    "process_scheduled_publications",
                    source_root=str(root),
                    publication_id=publication.pk,
                )

            publication.refresh_from_db()

            self.assertEqual(
                publication.status,
                ScheduledPublication.STATUS_PUBLISHED,
            )

            self.assertIsNotNone(publication.feed_post)
            self.assertEqual(
                publication.feed_post.content,
                original,
            )
            self.assertEqual(
                publication.campaign_key,
                "",
            )
            self.assertFalse((root / relative).exists())

        print("Unmarked legacy caption: PRESERVED")
        print("Unexpected suffix insertion: NONE")
        print("Original publication marker: PRESERVED")
