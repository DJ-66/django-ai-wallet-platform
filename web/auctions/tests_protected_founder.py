from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from auctions.founder_services import (
    create_founder_listing,
    purchase_tienda_fixed_listing,
    transfer_founder_ownership,
)
from auctions.models import (
    BidWallet,
    FounderAccount,
    FounderListing,
)


class ProtectedFounderTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.dj = User.objects.create_user(
            username="DJ",
            password="test",
        )
        self.platform = User.objects.create_user(
            username="platform",
            password="test",
        )
        self.buyer = User.objects.create_user(
            username="buyer",
            password="test",
        )

        BidWallet.objects.create(
            user=self.dj,
            credits=100_000,
        )
        BidWallet.objects.create(
            user=self.platform,
            credits=0,
        )
        BidWallet.objects.create(
            user=self.buyer,
            credits=200_000,
        )

    def test_dj_cannot_be_listed_p2p(self):
        founder = FounderAccount.objects.create(
            handle="dj",
            owner_root=self.dj,
            current_account=self.dj,
            status=FounderAccount.STATUS_OWNED,
        )

        with self.assertRaises(ValidationError):
            create_founder_listing(
                founder_account=founder,
                seller=self.dj,
                sale_type=FounderListing.SALE_FIXED,
                fixed_price_credits=100_000,
            )

        self.assertFalse(
            FounderListing.objects.filter(
                founder_account=founder,
                status=FounderListing.STATUS_ACTIVE,
            ).exists()
        )

    def test_dj_cannot_transfer_ownership(self):
        founder = FounderAccount.objects.create(
            handle="dj",
            owner_root=self.dj,
            current_account=self.dj,
            status=FounderAccount.STATUS_OWNED,
        )

        with self.assertRaises(ValidationError):
            transfer_founder_ownership(
                founder_account=founder,
                buyer=self.buyer,
                sale_price_credits=1_000,
            )

        founder.refresh_from_db()

        self.assertEqual(
            founder.owner_root_id,
            self.dj.pk,
        )

    def test_stale_dj_tienda_listing_cannot_be_purchased(self):
        founder = FounderAccount.objects.create(
            handle="dj",
            owner_root=self.platform,
            status=FounderAccount.STATUS_LISTED,
        )

        listing = FounderListing.objects.create(
            founder_account=founder,
            seller_root=self.platform,
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_FIXED,
            sale_type=FounderListing.SALE_FIXED,
            fixed_price_credits=100_000,
            status=FounderListing.STATUS_ACTIVE,
        )

        before = self.buyer.bidwallet.credits

        with self.assertRaises(ValidationError):
            purchase_tienda_fixed_listing(
                listing=listing,
                buyer=self.buyer,
            )

        founder.refresh_from_db()
        listing.refresh_from_db()
        self.buyer.bidwallet.refresh_from_db()

        self.assertEqual(
            founder.owner_root_id,
            self.platform.pk,
        )
        self.assertEqual(
            listing.status,
            FounderListing.STATUS_ACTIVE,
        )
        self.assertEqual(
            self.buyer.bidwallet.credits,
            before,
        )
