"""Regression tests for safe Founder Tienda Blind Offer recovery."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auctions.founder_blind_replenishment import (
    replenish_blind_offers,
)
from auctions.founder_services import (
    close_founder_blind_listing,
)
from auctions.management.commands.replenish_founder_tienda import (
    BLIND_HANDLES,
    BLIND_RESERVE_HANDLES,
)
from auctions.models import (
    FounderAccount,
    FounderListing,
)
from auctions.utils import get_system_wallet


class BlindReplenishmentTests(TestCase):

    def setUp(self):
        self.platform = get_system_wallet().user
        self.curated = BLIND_HANDLES + BLIND_RESERVE_HANDLES

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

    def seed(self, count):
        return [
            self.asset(handle)
            for handle in self.curated[:count]
        ]

    def active_blind(self):
        return FounderListing.objects.filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_BLIND,
            status=FounderListing.STATUS_ACTIVE,
        )

    def historical(self, asset, **overrides):
        now = timezone.now()

        values = {
            "founder_account": asset,
            "seller_root": self.platform,
            "listing_source": FounderListing.SOURCE_TIENDA,
            "tienda_lane": FounderListing.TIENDA_BLIND,
            "sale_type": FounderListing.SALE_BLIND,
            "minimum_bid_credits": 500,
            "starts_at": now - timedelta(days=4),
            "ends_at": now - timedelta(days=1),
            "status": FounderListing.STATUS_EXPIRED,
        }
        values.update(overrides)

        return FounderListing.objects.create(**values)

    def test_empty_inventory_recovers_to_ten(self):
        self.seed(15)

        result = replenish_blind_offers()

        self.assertEqual(result["active_before"], 0)
        self.assertEqual(result["created"], 10)
        self.assertEqual(result["active_after"], 10)
        self.assertEqual(result["shortage"], 0)
        self.assertEqual(self.active_blind().count(), 10)
        self.assertEqual(len(set(result["handles"])), 10)

    def test_repeated_execution_is_idempotent(self):
        self.seed(15)
        replenish_blind_offers()

        before = list(
            self.active_blind()
            .order_by("pk")
            .values()
        )

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["shortage"], 0)

        self.assertEqual(
            before,
            list(self.active_blind().order_by("pk").values()),
        )

    def test_partial_inventory_fills_only_missing_slots(self):
        self.seed(15)
        replenish_blind_offers()

        expired = list(self.active_blind()[:3])

        for listing in expired:
            listing.ends_at = (
                timezone.now() - timedelta(seconds=1)
            )
            listing.save(update_fields=["ends_at"])

            close_founder_blind_listing(listing=listing)

        preserved = list(
            self.active_blind().values_list("pk", flat=True)
        )

        self.assertEqual(len(preserved), 7)

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 3)
        self.assertEqual(self.active_blind().count(), 10)

        self.assertEqual(
            self.active_blind().filter(pk__in=preserved).count(),
            7,
        )

    def test_shortage_commits_available_inventory(self):
        self.seed(4)

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 4)
        self.assertEqual(result["active_after"], 4)
        self.assertEqual(result["shortage"], 6)
        self.assertEqual(self.active_blind().count(), 4)

    def test_no_candidates_reports_shortage(self):
        result = replenish_blind_offers()

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["shortage"], 10)
        self.assertEqual(FounderAccount.objects.count(), 0)

    def test_preserves_three_day_duration_and_floor(self):
        asset = self.asset(
            self.curated[0],
            floor_price_credits=750,
        )

        replenish_blind_offers()

        listing = self.active_blind().get(
            founder_account=asset
        )

        self.assertEqual(
            listing.ends_at - listing.starts_at,
            timedelta(days=3),
        )
        self.assertEqual(listing.minimum_bid_credits, 750)
        self.assertEqual(
            listing.seller_root_id,
            self.platform.pk,
        )

        asset.refresh_from_db()

        self.assertEqual(
            asset.status,
            FounderAccount.STATUS_LISTED,
        )
        self.assertEqual(
            asset.owner_root_id,
            self.platform.pk,
        )
        self.assertEqual(asset.floor_price_credits, 750)

    def test_minimum_bid_is_five_hundred(self):
        self.seed(1)
        replenish_blind_offers()

        self.assertEqual(
            self.active_blind().get().minimum_bid_credits,
            500,
        )

    def test_fresh_inventory_preferred(self):
        assets = self.seed(15)

        for asset in assets[:5]:
            self.historical(asset)

        replenish_blind_offers()

        selected = set(
            self.active_blind()
            .values_list("founder_account_id", flat=True)
        )

        self.assertEqual(
            selected,
            {asset.pk for asset in assets[5:]},
        )

    def test_expired_inventory_can_be_reused(self):
        assets = self.seed(10)

        for asset in assets:
            self.historical(asset)

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 10)
        self.assertEqual(self.active_blind().count(), 10)

        self.assertEqual(
            FounderListing.objects.filter(
                status=FounderListing.STATUS_EXPIRED
            ).count(),
            10,
        )

    def test_private_unowned_reserved_and_occupied_excluded(self):
        User = get_user_model()

        private = User.objects.create_user(
            username="private-owner-test"
        )

        occupied = User.objects.create_user(
            username="occupied-account-test"
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
                current_account=occupied,
            ),
            self.asset(
                self.curated[4],
                status=FounderAccount.STATUS_OWNED,
            ),
        ]

        User.objects.create_user(
            username=self.curated[5].upper()
        )

        excluded.append(self.asset(self.curated[5]))

        safe = self.asset(self.curated[6])

        before = list(
            FounderAccount.objects.filter(
                pk__in=[asset.pk for asset in excluded]
            ).order_by("pk").values()
        )

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 1)
        self.assertEqual(
            self.active_blind().get().founder_account_id,
            safe.pk,
        )

        self.assertEqual(
            before,
            list(
                FounderAccount.objects.filter(
                    pk__in=[asset.pk for asset in excluded]
                ).order_by("pk").values()
            ),
        )

    def test_noncurated_inventory_excluded(self):
        self.asset("zzzz")
        self.seed(1)

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 1)
        self.assertNotIn("zzzz", result["handles"])

    def test_protected_identity_excluded(self):
        protected = self.asset("dj")

        with patch(
            "auctions.management.commands."
            "replenish_founder_tienda.BLIND_HANDLES",
            ["dj"],
        ):
            with patch(
                "auctions.management.commands."
                "replenish_founder_tienda.BLIND_RESERVE_HANDLES",
                [],
            ):
                result = replenish_blind_offers()

        self.assertEqual(result["created"], 0)

        protected.refresh_from_db()

        self.assertEqual(
            protected.status,
            FounderAccount.STATUS_TREASURY,
        )

    def test_existing_fixed_listing_excluded_and_preserved(self):
        asset = self.asset(
            self.curated[0],
            status=FounderAccount.STATUS_LISTED,
        )

        fixed = FounderListing.objects.create(
            founder_account=asset,
            seller_root=self.platform,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_FIXED,
            sale_type=FounderListing.SALE_FIXED,
            fixed_price_credits=1000,
            status=FounderListing.STATUS_ACTIVE,
        )

        before = FounderListing.objects.filter(
            pk=fixed.pk
        ).values().get()

        self.asset(self.curated[1])

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 1)

        self.assertEqual(
            before,
            FounderListing.objects.filter(
                pk=fixed.pk
            ).values().get(),
        )

    def test_unresolved_expired_active_listing_occupies_slot(self):
        self.seed(15)
        replenish_blind_offers()

        listing = self.active_blind().first()

        listing.ends_at = (
            timezone.now() - timedelta(seconds=1)
        )
        listing.save(update_fields=["ends_at"])

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 0)
        self.assertEqual(self.active_blind().count(), 10)

        listing.refresh_from_db()

        self.assertEqual(
            listing.status,
            FounderListing.STATUS_ACTIVE,
        )

    def test_replenishment_does_not_provision_properties(self):
        self.seed(15)

        before = FounderAccount.objects.count()

        replenish_blind_offers()

        self.assertEqual(
            FounderAccount.objects.count(),
            before,
        )
