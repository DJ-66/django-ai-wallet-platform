"""Concurrent execution safety for FANZ AI scheduling."""

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import close_old_connections
from django.test import TransactionTestCase

from auctions.models import ScheduledPublication
from auctions.management.commands import generate_ai_publications
from auctions.tests_phase14.test_generate_ai_publications import (
    write_image,
)


class ConcurrentAISchedulerTests(TransactionTestCase):

    def test_two_schedulers_queue_only_one_post(self):
        user = get_user_model().objects.create_user(
            username="ConcurrentSchedulerTest",
            password="test-only-password",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            write_image(root / "PackA" / "post-1.jpg")
            write_image(root / "PackA" / "post-2.jpg")

            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "creators": [{
                    "account": user.username,
                    "packs": ["PackA"],
                    "avatar_source": None,
                    "bio": "Playful fictional creator",
                    "post_style": {
                        "hashtags": [
                            "Lifestyle",
                            "Style",
                            "AIInfluencer",
                            "DigitalCreator",
                            "CreatorLife",
                            "Fashion",
                        ],
                    },
                }],
            }))

            barrier = Barrier(2)

            def generate_copy(**kwargs):
                barrier.wait(timeout=15)
                return {
                    "title": "Concurrent story",
                    "caption": "A little adventure today.",
                    "hashtags": [
                        "Lifestyle",
                        "Style",
                        "DigitalCreator",
                        "CreatorLife",
                    ],
                }

            def prepare_caption(**kwargs):
                from auctions.ai_services.legacy_publication_preparation import (
                    plan_publication_ending,
                )

                plan = plan_publication_ending(
                    username=kwargs["username"],
                    publication_key=kwargs["publication_key"],
                    sequence=kwargs["sequence"],
                )

                return (
                    kwargs["content"].replace(
                        "\n\n",
                        "\nTell me your story in my DMs.\n\n",
                        1,
                    ),
                    plan,
                )

            def run_scheduler():
                close_old_connections()
                try:
                    call_command(
                        "generate_ai_publications",
                        source_root=str(root),
                        seed=14,
                        start_delay_minutes=60,
                    )
                finally:
                    close_old_connections()

            with (
                patch.object(
                    generate_ai_publications,
                    "MANIFEST_PATH",
                    manifest,
                ),
                patch.object(
                    generate_ai_publications,
                    "generate_creator_post_copy",
                    side_effect=generate_copy,
                ),
                patch(
                    "auctions.ai_services.legacy_claimed_preparation."
                    "prepare_ai_caption",
                    side_effect=prepare_caption,
                ),
                patch.object(
                    generate_ai_publications.settings,
                    "CREATOR_VISION_COPY_ENABLED",
                    True,
                ),
                patch.dict(
                    "os.environ",
                    {"FANZ_LEGACY_AI_SUFFIX_ENABLED": "true"},
                ),
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [
                        executor.submit(run_scheduler)
                        for _ in range(2)
                    ]
                    for future in futures:
                        future.result(timeout=45)

        publications = ScheduledPublication.objects.filter(
            creator=user,
            publication_key__startswith="ai:",
        )

        self.assertEqual(publications.count(), 1)

        publication = publications.get()

        self.assertEqual(
            publication.status,
            ScheduledPublication.STATUS_QUEUED,
        )
        self.assertEqual(
            publication.campaign_key,
            "ai_gemma4",
        )

        print("Concurrent scheduler workers: 2")
        print("Queued publications: 1")
        print("Duplicate publications: 0")
        print("Scheduler concurrency: PASS")
