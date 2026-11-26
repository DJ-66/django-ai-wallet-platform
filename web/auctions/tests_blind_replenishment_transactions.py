"""PostgreSQL transaction and inventory safety tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from itertools import product
from threading import Barrier, Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from auctions.founder_blind_replenishment import (
    replenish_blind_offers,
)
from auctions.management.commands.replenish_founder_tienda import (
    BLIND_HANDLES,
    BLIND_RESERVE_HANDLES,
)
from auctions.models import (
    BidWallet,
    FounderAccount,
    FounderCart,
    FounderCartItem,
    FounderBid,
    FounderCreditHold,
    FounderListing,
    FounderVendingHold,
)
from auctions.utils import get_system_wallet


class BlindReplenishmentTransactionTests(TransactionTestCase):

    def setUp(self):
        self.platform = get_system_wallet().user
        self.curated = BLIND_HANDLES + BLIND_RESERVE_HANDLES

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

    def worker(self, operation):
        connections.close_all()

        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '10s'")
                cursor.execute("SET statement_timeout = '20s'")

            return operation()

        finally:
            connections.close_all()

    def test_two_concurrent_workers_create_only_ten(self):
        self.seed(20)
        barrier = Barrier(2)

        def replenish():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]

            barrier.wait(timeout=10)

            return pid, replenish_blind_offers()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.worker, replenish)
                for _ in range(2)
            ]

            results = [
                future.result(timeout=30)
                for future in futures
            ]

        self.assertNotEqual(
            results[0][0],
            results[1][0],
        )

        self.assertEqual(
            sorted(result["created"] for _, result in results),
            [0, 10],
        )

        self.assertEqual(self.active_blind().count(), 10)

        self.assertEqual(
            self.active_blind()
            .values("founder_account_id")
            .distinct()
            .count(),
            10,
        )

    def test_locked_candidate_is_skipped(self):
        assets = self.seed(2)
        locked = Event()
        release = Event()

        def hold_asset():
            with transaction.atomic():
                FounderAccount.objects.select_for_update().get(
                    pk=assets[0].pk
                )

                locked.set()

                if not release.wait(timeout=20):
                    raise RuntimeError("Lock release timed out")

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.worker, hold_asset)

            try:
                self.assertTrue(locked.wait(timeout=10))

                result = replenish_blind_offers()

                self.assertEqual(result["created"], 1)
                self.assertEqual(
                    result["handles"],
                    [assets[1].handle],
                )

            finally:
                release.set()
                future.result(timeout=25)

        assets[0].refresh_from_db()

        self.assertEqual(
            assets[0].status,
            FounderAccount.STATUS_TREASURY,
        )

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 1)
        self.assertEqual(self.active_blind().count(), 2)

    def test_partial_replenishment_commits_across_connections(self):
        self.seed(4)

        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(
                self.worker,
                replenish_blind_offers,
            ).result(timeout=30)

        self.assertEqual(result["created"], 4)
        self.assertEqual(result["shortage"], 6)

        # Main connection observes the worker's committed rows.
        self.assertEqual(self.active_blind().count(), 4)

    def test_active_vending_quote_excludes_candidate(self):
        blocked, safe = self.seed(2)

        buyer = get_user_model().objects.create_user(
            username="wp05-quote-buyer"
        )

        cart = FounderCart.objects.create(
            purchaser=buyer
        )

        now = timezone.now()

        item = FounderCartItem.objects.create(
            cart=cart,
            wanted_handle=blocked.handle,
            budget_credits=1000,
            list_price_credits=500,
            status=FounderCartItem.STATUS_QUOTED,
            quoted_at=now,
            reservation_expires_at=now + timedelta(minutes=15),
        )

        before = FounderCartItem.objects.filter(
            pk=item.pk
        ).values().get()

        result = replenish_blind_offers()

        self.assertEqual(result["handles"], [safe.handle])

        self.assertEqual(
            before,
            FounderCartItem.objects.filter(
                pk=item.pk
            ).values().get(),
        )

        blocked.refresh_from_db()

        self.assertEqual(
            blocked.status,
            FounderAccount.STATUS_TREASURY,
        )

    def test_held_vending_credits_exclude_expired_quote(self):
        blocked, safe = self.seed(2)

        buyer = get_user_model().objects.create_user(
            username="wp05-hold-buyer"
        )

        wallet = BidWallet.objects.create(
            user=buyer,
            credits=900,
        )

        cart = FounderCart.objects.create(
            purchaser=buyer
        )

        now = timezone.now()

        item = FounderCartItem.objects.create(
            cart=cart,
            wanted_handle=blocked.handle,
            budget_credits=600,
            list_price_credits=500,
            status=FounderCartItem.STATUS_QUOTED,
            quoted_at=now - timedelta(hours=1),
            reservation_expires_at=now - timedelta(minutes=1),
        )

        hold = FounderVendingHold.objects.create(
            cart_item=item,
            wallet=wallet,
            amount_credits=600,
            status=FounderVendingHold.STATUS_HELD,
        )

        before = FounderVendingHold.objects.filter(
            pk=hold.pk
        ).values().get()

        result = replenish_blind_offers()

        self.assertEqual(result["handles"], [safe.handle])

        self.assertEqual(
            before,
            FounderVendingHold.objects.filter(
                pk=hold.pk
            ).values().get(),
        )

        wallet.refresh_from_db()

        self.assertEqual(wallet.credits, 900)

    def test_expanded_fixed_and_wasteland_inventory_preserved(self):
        self.seed(15)

        # Synthetic four-character handles, separate from
        # the curated Blind Offer inventory.
        handles = (
            "z" + "".join(chars)
            for chars in product(
                "abcdefghijklmnopqrstuvwxyz",
                repeat=3,
            )
        )

        fixed_assets = [
            self.asset(
                next(handles),
                status=FounderAccount.STATUS_LISTED,
            )
            for _ in range(1647)
        ]

        swamp_assets = [
            self.asset(
                next(handles),
                status=FounderAccount.STATUS_LISTED,
            )
            for _ in range(10)
        ]

        listings = []

        for asset in fixed_assets:
            listings.append(
                FounderListing(
                    founder_account=asset,
                    seller_root=self.platform,
                    listing_source=FounderListing.SOURCE_TIENDA,
                    tienda_lane=FounderListing.TIENDA_FIXED,
                    sale_type=FounderListing.SALE_FIXED,
                    fixed_price_credits=1000,
                    status=FounderListing.STATUS_ACTIVE,
                )
            )

        for asset in swamp_assets:
            listings.append(
                FounderListing(
                    founder_account=asset,
                    seller_root=self.platform,
                    listing_source=FounderListing.SOURCE_TIENDA,
                    tienda_lane=FounderListing.TIENDA_SWAMP,
                    sale_type=FounderListing.SALE_FIXED,
                    fixed_price_credits=200,
                    status=FounderListing.STATUS_ACTIVE,
                )
            )

        FounderListing.objects.bulk_create(listings)

        preserved = FounderListing.objects.exclude(
            tienda_lane=FounderListing.TIENDA_BLIND
        ).order_by("pk")

        before = list(preserved.values())

        asset_ids = [
            asset.pk
            for asset in fixed_assets + swamp_assets
        ]

        assets_before = list(
            FounderAccount.objects.filter(
                pk__in=asset_ids
            ).order_by("pk").values()
        )

        result = replenish_blind_offers()

        self.assertEqual(result["created"], 10)
        self.assertEqual(self.active_blind().count(), 10)
        self.assertEqual(len(before), 1657)
        self.assertEqual(before, list(preserved.values()))

        self.assertEqual(
            assets_before,
            list(
                FounderAccount.objects.filter(
                    pk__in=asset_ids
                ).order_by("pk").values()
            ),
        )

    def test_oldest_previous_inventory_preferred(self):
        assets = self.seed(12)
        now = timezone.now()

        for index, asset in enumerate(assets):
            listing = FounderListing.objects.create(
                founder_account=asset,
                seller_root=self.platform,
                listing_source=FounderListing.SOURCE_TIENDA,
                tienda_lane=FounderListing.TIENDA_BLIND,
                sale_type=FounderListing.SALE_BLIND,
                minimum_bid_credits=500,
                starts_at=now - timedelta(days=30),
                ends_at=now - timedelta(days=27),
                status=FounderListing.STATUS_EXPIRED,
            )

            FounderListing.objects.filter(
                pk=listing.pk
            ).update(
                created_at=now - timedelta(days=30-index)
            )

        result = replenish_blind_offers()

        self.assertEqual(
            set(result["handles"]),
            {asset.handle for asset in assets[:10]},
        )

    def test_fresh_selection_uses_shuffle_order(self):
        assets = self.seed(15)

        def reverse_order(values):
            values.reverse()

        with patch(
            "auctions.founder_blind_replenishment.random.shuffle",
            side_effect=reverse_order,
        ) as shuffle:
            result = replenish_blind_offers()

        self.assertTrue(shuffle.called)

        self.assertEqual(
            result["handles"],
            [asset.handle for asset in reversed(assets[-10:])],
        )

        self.assertEqual(len(set(result["handles"])), 10)


    def historical_listing(self, asset, status):
        now = timezone.now()

        return FounderListing.objects.create(
            founder_account=asset,
            seller_root=self.platform,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_BLIND,
            sale_type=FounderListing.SALE_BLIND,
            minimum_bid_credits=500,
            starts_at=now - timedelta(days=4),
            ends_at=now - timedelta(days=1),
            status=status,
        )

    def test_previously_sold_property_is_not_recycled(self):
        blocked, safe = self.seed(2)

        sold = self.historical_listing(
            blocked,
            FounderListing.STATUS_SOLD,
        )

        before = FounderListing.objects.filter(
            pk=sold.pk
        ).values().get()

        result = replenish_blind_offers()

        self.assertEqual(result["handles"], [safe.handle])

        self.assertEqual(
            before,
            FounderListing.objects.filter(
                pk=sold.pk
            ).values().get(),
        )

        blocked.refresh_from_db()

        self.assertEqual(
            blocked.status,
            FounderAccount.STATUS_TREASURY,
        )

    def test_unresolved_active_historical_bid_excludes_property(self):
        blocked, safe = self.seed(2)

        listing = self.historical_listing(
            blocked,
            FounderListing.STATUS_EXPIRED,
        )

        buyer = get_user_model().objects.create_user(
            username="wp05-active-bid-buyer"
        )

        bid = FounderBid.objects.create(
            listing=listing,
            bidder_root=buyer,
            amount_credits=600,
            status=FounderBid.STATUS_ACTIVE,
        )

        before = FounderBid.objects.filter(
            pk=bid.pk
        ).values().get()

        result = replenish_blind_offers()

        self.assertEqual(result["handles"], [safe.handle])

        self.assertEqual(
            before,
            FounderBid.objects.filter(
                pk=bid.pk
            ).values().get(),
        )

    def test_held_historical_bid_credits_exclude_property(self):
        blocked, safe = self.seed(2)

        listing = self.historical_listing(
            blocked,
            FounderListing.STATUS_EXPIRED,
        )

        buyer = get_user_model().objects.create_user(
            username="wp05-bid-hold-buyer"
        )

        wallet = BidWallet.objects.create(
            user=buyer,
            credits=900,
        )

        bid = FounderBid.objects.create(
            listing=listing,
            bidder_root=buyer,
            amount_credits=600,
            status=FounderBid.STATUS_LOST,
        )

        hold = FounderCreditHold.objects.create(
            bid=bid,
            wallet=wallet,
            amount_credits=600,
            status=FounderCreditHold.STATUS_HELD,
        )

        hold_before = FounderCreditHold.objects.filter(
            pk=hold.pk
        ).values().get()

        bid_before = FounderBid.objects.filter(
            pk=bid.pk
        ).values().get()

        result = replenish_blind_offers()

        self.assertEqual(result["handles"], [safe.handle])

        self.assertEqual(
            hold_before,
            FounderCreditHold.objects.filter(
                pk=hold.pk
            ).values().get(),
        )

        self.assertEqual(
            bid_before,
            FounderBid.objects.filter(
                pk=bid.pk
            ).values().get(),
        )

        wallet.refresh_from_db()

        self.assertEqual(wallet.credits, 900)

    def test_released_historical_hold_allows_safe_reuse(self):
        asset = self.seed(1)[0]

        listing = self.historical_listing(
            asset,
            FounderListing.STATUS_EXPIRED,
        )

        buyer = get_user_model().objects.create_user(
            username="wp05-released-hold-buyer"
        )

        wallet = BidWallet.objects.create(
            user=buyer,
            credits=1500,
        )

        bid = FounderBid.objects.create(
            listing=listing,
            bidder_root=buyer,
            amount_credits=600,
            status=FounderBid.STATUS_LOST,
        )

        hold = FounderCreditHold.objects.create(
            bid=bid,
            wallet=wallet,
            amount_credits=600,
            status=FounderCreditHold.STATUS_RELEASED,
        )

        before = FounderCreditHold.objects.filter(
            pk=hold.pk
        ).values().get()

        result = replenish_blind_offers()

        self.assertEqual(result["handles"], [asset.handle])

        self.assertEqual(
            before,
            FounderCreditHold.objects.filter(
                pk=hold.pk
            ).values().get(),
        )

        wallet.refresh_from_db()

        self.assertEqual(wallet.credits, 1500)
