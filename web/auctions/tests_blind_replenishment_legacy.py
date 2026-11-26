"""Legacy Tienda compatibility and shared-lock regression tests."""

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from itertools import product
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, connections
from django.test import TransactionTestCase

from auctions.founder_blind_replenishment import (
    replenish_blind_offers,
)
from auctions.founder_tienda import replenish_founder_tienda
from auctions.management.commands.replenish_founder_tienda import (
    BLIND_HANDLES,
    BLIND_RESERVE_HANDLES,
)
from auctions.models import FounderAccount, FounderListing
from auctions.utils import get_system_wallet


class LegacyTiendaCompatibilityTests(TransactionTestCase):

    def setUp(self):
        self.platform = get_system_wallet().user

        self.curated = (
            BLIND_HANDLES + BLIND_RESERVE_HANDLES
        )

        self.assertEqual(connection.vendor, "postgresql")

    def asset(self, handle, **overrides):
        values = {
            "owner_root": self.platform,
            "status": FounderAccount.STATUS_TREASURY,
            "floor_price_credits": 200,
        }

        values.update(overrides)

        return FounderAccount.objects.create(
            handle=handle,
            **values,
        )

    def active(self, lane):
        return FounderListing.objects.filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=lane,
            status=FounderListing.STATUS_ACTIVE,
        )

    def seed_fixed_lanes(self, fixed_count=10):
        handles = (
            "z" + "".join(chars)
            for chars in product(
                "abcdefghijklmnopqrstuvwxyz",
                repeat=3,
            )
        )

        listings = []

        for lane, count, price in [
            (
                FounderListing.TIENDA_FIXED,
                fixed_count,
                1000,
            ),
            (
                FounderListing.TIENDA_SWAMP,
                10,
                200,
            ),
        ]:
            for _ in range(count):
                asset = self.asset(
                    next(handles),
                    status=FounderAccount.STATUS_LISTED,
                )

                listings.append(
                    FounderListing(
                        founder_account=asset,
                        seller_root=self.platform,
                        listing_source=FounderListing.SOURCE_TIENDA,
                        tienda_lane=lane,
                        sale_type=FounderListing.SALE_FIXED,
                        fixed_price_credits=price,
                        status=FounderListing.STATUS_ACTIVE,
                    )
                )

        FounderListing.objects.bulk_create(listings)

    def run_legacy(self):
        output = StringIO()

        call_command(
            "replenish_founder_tienda",
            stdout=output,
        )

        return output.getvalue()

    def test_legacy_initial_provisioning_still_works(self):
        output = self.run_legacy()

        for lane in [
            FounderListing.TIENDA_FIXED,
            FounderListing.TIENDA_BLIND,
            FounderListing.TIENDA_SWAMP,
        ]:
            self.assertEqual(
                self.active(lane).count(),
                10,
            )

        self.assertIn(
            "MINIMUM TARGETS: READY",
            output,
        )

    def test_legacy_accepts_expanded_fixed_inventory(self):
        self.seed_fixed_lanes(fixed_count=1647)

        preserved = FounderListing.objects.all().order_by(
            "pk"
        )

        before = list(preserved.values())
        ids = [row["id"] for row in before]

        output = self.run_legacy()

        self.assertEqual(
            self.active(FounderListing.TIENDA_FIXED).count(),
            1647,
        )

        self.assertEqual(
            self.active(FounderListing.TIENDA_BLIND).count(),
            10,
        )

        self.assertEqual(
            self.active(FounderListing.TIENDA_SWAMP).count(),
            10,
        )

        self.assertEqual(
            before,
            list(
                preserved.filter(pk__in=ids).values()
            ),
        )

        self.assertIn(
            "MINIMUM TARGETS: READY",
            output,
        )

    def test_legacy_preserves_existing_property_state(self):
        private = get_user_model().objects.create_user(
            username="wp05-legacy-private"
        )

        linked = get_user_model().objects.create_user(
            username="wp05-legacy-linked"
        )

        excluded = [
            self.asset(
                self.curated[0],
                owner_root=private,
            ),
            self.asset(
                self.curated[1],
                owner_root=None,
            ),
            self.asset(
                self.curated[2],
                status=FounderAccount.STATUS_RESERVED,
            ),
            self.asset(
                self.curated[3],
                current_account=linked,
            ),
            self.asset(
                self.curated[4],
                status=FounderAccount.STATUS_OWNED,
                floor_price_credits=950,
            ),
        ]

        records = FounderAccount.objects.filter(
            pk__in=[asset.pk for asset in excluded]
        ).order_by("pk")

        before = list(records.values())

        self.run_legacy()

        self.assertEqual(
            before,
            list(records.values()),
        )

        self.assertFalse(
            FounderListing.objects.filter(
                founder_account__in=excluded
            ).exists()
        )

    def test_legacy_fallback_rejects_non_treasury(self):
        self.seed_fixed_lanes()

        private = get_user_model().objects.create_user(
            username="wp05-fallback-private"
        )

        excluded = [
            self.asset(
                "aaa",
                owner_root=private,
            ),
            self.asset(
                "aab",
                owner_root=None,
            ),
            self.asset(
                "aac",
                status=FounderAccount.STATUS_RESERVED,
            ),
            self.asset("dj"),
        ]

        for handle in self.curated[:10]:
            self.asset(handle)

        result = replenish_founder_tienda()

        self.assertEqual(
            result["blind_created"],
            10,
        )

        self.assertFalse(
            FounderListing.objects.filter(
                founder_account__in=excluded
            ).exists()
        )

    def test_legacy_shortage_rolls_back_without_provisioning(self):
        self.seed_fixed_lanes()

        for handle in self.curated[:4]:
            self.asset(handle)

        before = list(
            FounderAccount.objects.order_by("pk").values()
        )

        with self.assertRaises(ValidationError):
            replenish_founder_tienda()

        self.assertEqual(
            self.active(FounderListing.TIENDA_BLIND).count(),
            0,
        )

        self.assertEqual(
            before,
            list(
                FounderAccount.objects.order_by("pk").values()
            ),
        )

    def test_legacy_and_automatic_workers_share_lock(self):
        self.seed_fixed_lanes()

        for handle in self.curated[:20]:
            self.asset(handle)

        barrier = Barrier(2)

        def worker(operation):
            connections.close_all()

            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET lock_timeout = '10s'"
                    )
                    cursor.execute(
                        "SET statement_timeout = '30s'"
                    )
                    cursor.execute(
                        "SELECT pg_backend_pid()"
                    )

                    pid = cursor.fetchone()[0]

                barrier.wait(timeout=10)

                operation()

                return pid

            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    worker,
                    self.run_legacy,
                ),
                executor.submit(
                    worker,
                    replenish_blind_offers,
                ),
            ]

            pids = [
                future.result(timeout=45)
                for future in futures
            ]

        self.assertNotEqual(pids[0], pids[1])

        active = self.active(
            FounderListing.TIENDA_BLIND
        )

        self.assertEqual(active.count(), 10)

        self.assertEqual(
            active.values("founder_account_id")
            .distinct().count(),
            10,
        )

        self.assertEqual(
            self.active(FounderListing.TIENDA_FIXED).count(),
            10,
        )

        self.assertEqual(
            self.active(FounderListing.TIENDA_SWAMP).count(),
            10,
        )

    def test_repeated_legacy_execution_preserves_listings(self):
        self.run_legacy()

        before = list(
            FounderListing.objects.order_by("pk").values()
        )

        self.run_legacy()

        self.assertEqual(
            before,
            list(
                FounderListing.objects.order_by("pk").values()
            ),
        )
