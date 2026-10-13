import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone

from auctions.ai_services import creator_caption_recovery as recovery
from auctions.models import (
    CreatorCaptionRecoveryState,
    ScheduledPublication,
)


User = get_user_model()


class CreatorCaptionRecoveryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.manifest = Path(self.tempdir.name) / "manifest.json"
        self.manifest.write_text(json.dumps({
            "creators": [{"account": "CreatorA"}],
        }))

        self.creator = User.objects.create_user(
            username="CreatorA",
        )

        self.publication = ScheduledPublication.objects.create(
            publication_key="ai:creatora:concurrency",
            creator=self.creator,
            source_path="creator.jpg",
            title="From the Collection",
            content="A new favorite from the collection.",
            scheduled_for=timezone.now() + timedelta(hours=1),
            status=ScheduledPublication.STATUS_QUEUED,
        )

    def test_simultaneous_claims_are_unique(self):
        barrier = Barrier(2)

        def worker():
            close_old_connections()

            try:
                barrier.wait(timeout=10)

                return recovery.claim_next_publication(
                    lease_minutes=30,
                )
            finally:
                close_old_connections()

        with patch(
            "auctions.management.commands."
            "generate_ai_publications.MANIFEST_PATH",
            self.manifest,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(worker)
                    for _ in range(2)
                ]

                results = [
                    future.result(timeout=20)
                    for future in futures
                ]

        claimed = [
            result for result in results
            if result is not None
        ]

        self.assertEqual(len(claimed), 1)
        self.assertEqual(
            claimed[0][0],
            self.publication.pk,
        )

        self.assertEqual(
            CreatorCaptionRecoveryState.objects.filter(
                publication=self.publication,
            ).count(),
            1,
        )

        self.assertTrue(
            recovery.verify_claim(*claimed[0])
        )
