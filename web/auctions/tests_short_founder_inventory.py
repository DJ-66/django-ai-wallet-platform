from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auctions.fanz_search import _search_founder_accounts
from auctions.models import FounderAccount, FounderListing


class ShortFounderInventoryTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.platform = User.objects.create_user(
            username="platform",
            password="test-password",
        )

    def _founder(self, handle, price):
        founder = FounderAccount.objects.create(
            handle=handle,
            owner_root=self.platform,
            status=FounderAccount.STATUS_LISTED,
            floor_price_credits=200,
        )

        listing = FounderListing.objects.create(
            founder_account=founder,
            seller_root=self.platform,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_FIXED,
            sale_type=FounderListing.SALE_FIXED,
            fixed_price_credits=price,
            status=FounderListing.STATUS_ACTIVE,
        )

        return founder, listing

    def test_short_founder_is_searchable_with_active_100k_listing(self):
        founder, listing = self._founder(
            "xo",
            100000,
        )

        results = _search_founder_accounts("xo", 10)

        self.assertTrue(
            any(
                row["title"].casefold() == "@xo"
                for row in results
            )
        )

        self.assertEqual(
            founder.owner_root,
            self.platform,
        )
        self.assertEqual(
            listing.fixed_price_credits,
            100000,
        )
        self.assertEqual(
            listing.listing_source,
            FounderListing.SOURCE_TIENDA,
        )
        self.assertEqual(
            listing.tienda_lane,
            FounderListing.TIENDA_FIXED,
        )


class PremiumFounderDisplayTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.platform = User.objects.create_user(
            username="platform",
            password="test-password",
        )

        self.viewer = User.objects.create_user(
            username="viewer1",
            password="test-password",
        )

    def _listing(self, handle, price):
        founder = FounderAccount.objects.create(
            handle=handle,
            owner_root=self.platform,
            status=FounderAccount.STATUS_LISTED,
            floor_price_credits=200,
        )

        return FounderListing.objects.create(
            founder_account=founder,
            seller_root=self.platform,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_FIXED,
            sale_type=FounderListing.SALE_FIXED,
            fixed_price_credits=price,
            status=FounderListing.STATUS_ACTIVE,
        )

    def test_premium_display_is_five_regular_plus_five_short(self):
        regular = (
            "alex",
            "cats",
            "dogs",
            "love",
            "star",
            "wolf",
        )

        short = (
            "ai",
            "go",
            "tv",
            "vc",
            "vr",
            "xo",
        )

        for handle in regular:
            self._listing(handle, 1000)

        for handle in short:
            self._listing(handle, 100000)

        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse("founder_tienda")
        )

        self.assertEqual(response.status_code, 200)

        fixed = list(
            response.context["fixed_listings"]
        )

        self.assertEqual(len(fixed), 10)

        short_count = sum(
            1
            for listing in fixed
            if listing.founder_account.handle_length <= 2
        )

        regular_count = sum(
            1
            for listing in fixed
            if listing.founder_account.handle_length >= 3
        )

        self.assertEqual(short_count, 5)
        self.assertEqual(regular_count, 5)

        prices = [
            listing.fixed_price_credits
            for listing in fixed
        ]

        self.assertEqual(
            prices,
            sorted(prices),
        )

    def test_hidden_short_inventory_remains_active(self):
        for handle in (
            "ai",
            "go",
            "tv",
            "vc",
            "vr",
            "xo",
        ):
            self._listing(handle, 100000)

        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse("founder_tienda")
        )

        displayed = {
            listing.founder_account.handle
            for listing in response.context[
                "fixed_listings"
            ]
        }

        self.assertEqual(len(displayed), 5)

        self.assertEqual(
            FounderListing.objects.filter(
                founder_account__handle_length__lte=2,
                listing_source=FounderListing.SOURCE_TIENDA,
                tienda_lane=FounderListing.TIENDA_FIXED,
                status=FounderListing.STATUS_ACTIVE,
            ).count(),
            6,
        )

        self.assertEqual(
            FounderListing.objects.filter(
                founder_account__handle="xo",
                status=FounderListing.STATUS_ACTIVE,
                fixed_price_credits=100000,
            ).count(),
            1,
        )
