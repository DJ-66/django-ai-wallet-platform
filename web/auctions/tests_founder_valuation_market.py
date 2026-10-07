from django.contrib.auth import get_user_model
from django.test import TestCase

from auctions.founder_valuation import get_founder_valuation
from auctions.models import (
    FounderAccount,
    FounderListing,
)


class FounderValuationMarketSeparationTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.dj = User.objects.create_user(
            username="DJ",
            password="test-password",
        )

    def _founder_with_listing(self, handle):
        founder = FounderAccount.objects.create(
            handle=handle,
            owner_root=self.dj,
            status=FounderAccount.STATUS_LISTED,
            floor_price_credits=200,
        )

        listing = FounderListing.objects.create(
            founder_account=founder,
            seller_root=self.dj,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_FIXED,
            sale_type=FounderListing.SALE_FIXED,
            fixed_price_credits=100_000,
            status=FounderListing.STATUS_ACTIVE,
        )

        return founder, listing

    def test_three_char_100k_asking_price_does_not_raise_valuation(self):
        founder, listing = self._founder_with_listing(
            "lya"
        )

        valuation = get_founder_valuation(founder)

        self.assertEqual(
            valuation["estimated_value"]["intrinsic"],
            260,
        )
        self.assertEqual(
            valuation["estimated_value"]["current"],
            260,
        )
        self.assertEqual(
            valuation["estimated_value"]["year_2"],
            520,
        )
        self.assertEqual(
            valuation["estimated_value"]["year_5"],
            1560,
        )
        self.assertEqual(
            valuation["estimated_value"]["year_10"],
            3900,
        )

        self.assertEqual(
            valuation["market"]["asking_price_credits"],
            100_000,
        )
        self.assertEqual(
            listing.fixed_price_credits,
            100_000,
        )

    def test_four_char_100k_asking_price_does_not_raise_valuation(self):
        founder, listing = self._founder_with_listing(
            "ruby"
        )

        valuation = get_founder_valuation(founder)

        self.assertEqual(
            valuation["estimated_value"]["intrinsic"],
            240,
        )
        self.assertEqual(
            valuation["estimated_value"]["current"],
            240,
        )
        self.assertEqual(
            valuation["estimated_value"]["year_2"],
            480,
        )
        self.assertEqual(
            valuation["estimated_value"]["year_5"],
            1440,
        )
        self.assertEqual(
            valuation["estimated_value"]["year_10"],
            3600,
        )

        self.assertEqual(
            valuation["market"]["asking_price_credits"],
            100_000,
        )
        self.assertEqual(
            listing.fixed_price_credits,
            100_000,
        )
