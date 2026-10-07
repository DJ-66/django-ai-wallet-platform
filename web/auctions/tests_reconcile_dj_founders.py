from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from auctions.models import FounderAccount, FounderListing


class ReconcileDJFoundersTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.dj = User.objects.create_user(
            username="DJ",
            password="test",
        )

        self.lya = User.objects.create_user(
            username="Lya",
            password="test",
        )

        self.luna = User.objects.create_user(
            username="luna",
            password="test",
        )

        self.other = User.objects.create_user(
            username="dj9",
            password="test",
        )

        # 5+ characters: must never become Founder inventory.
        self.long_user = User.objects.create_user(
            username="Alana",
            password="test",
        )

        self.luna_founder = FounderAccount.objects.create(
            handle="luna",
            owner_root=self.dj,
            status=FounderAccount.STATUS_LISTED,
        )

        self.luna_listing = FounderListing.objects.create(
            founder_account=self.luna_founder,
            seller_root=self.dj,
            listing_source=FounderListing.SOURCE_P2P,
            tienda_lane=None,
            sale_type=FounderListing.SALE_FIXED,
            fixed_price_credits=5_000,
            status=FounderListing.STATUS_ACTIVE,
        )

        self.foreign_founder = FounderAccount.objects.create(
            handle="dj9",
            owner_root=self.other,
            current_account=self.other,
            status=FounderAccount.STATUS_OWNED,
        )

    def _run(self, *, dry_run=False):
        stdout = StringIO()

        kwargs = {
            "owner": "DJ",
            "price": 100_000,
            "stdout": stdout,
        }

        if dry_run:
            kwargs["dry_run"] = True

        call_command(
            "reconcile_dj_founders",
            **kwargs,
        )

        return stdout.getvalue()

    def test_dry_run_does_not_mutate(self):
        output = self._run(dry_run=True)

        self.assertIn("@Lya", output)

        self.assertFalse(
            FounderAccount.objects.filter(
                handle__iexact="lya"
            ).exists()
        )

        self.luna_listing.refresh_from_db()

        self.assertEqual(
            self.luna_listing.fixed_price_credits,
            5_000,
        )

    def test_reconcile_creates_missing_founder_and_initial_listing(self):
        self._run()

        founder = FounderAccount.objects.get(
            handle__iexact="lya"
        )

        self.assertEqual(
            founder.owner_root_id,
            self.dj.pk,
        )
        self.assertEqual(
            founder.current_account_id,
            self.lya.pk,
        )
        self.assertEqual(
            founder.status,
            FounderAccount.STATUS_LISTED,
        )

        listing = FounderListing.objects.get(
            founder_account=founder,
            status=FounderListing.STATUS_ACTIVE,
        )

        self.assertEqual(
            listing.seller_root_id,
            self.dj.pk,
        )
        self.assertEqual(
            listing.listing_source,
            FounderListing.SOURCE_P2P,
        )
        self.assertIsNone(
            listing.tienda_lane,
        )
        self.assertEqual(
            listing.sale_type,
            FounderListing.SALE_FIXED,
        )
        self.assertEqual(
            listing.fixed_price_credits,
            100_000,
        )

    def test_existing_p2p_price_is_preserved(self):
        self._run()

        self.luna_listing.refresh_from_db()
        self.luna_founder.refresh_from_db()

        self.assertEqual(
            self.luna_listing.fixed_price_credits,
            5_000,
        )
        self.assertEqual(
            self.luna_founder.current_account_id,
            self.luna.pk,
        )

    def test_foreign_owned_founder_is_preserved(self):
        self._run()

        self.foreign_founder.refresh_from_db()

        self.assertEqual(
            self.foreign_founder.owner_root_id,
            self.other.pk,
        )
        self.assertEqual(
            self.foreign_founder.current_account_id,
            self.other.pk,
        )

        self.assertFalse(
            FounderListing.objects.filter(
                founder_account=self.foreign_founder,
                status=FounderListing.STATUS_ACTIVE,
            ).exists()
        )

    def test_five_plus_character_account_is_excluded(self):
        self._run()

        self.assertFalse(
            FounderAccount.objects.filter(
                handle__iexact="Alana"
            ).exists()
        )

    def test_protected_dj_founder_is_not_created_or_listed(self):
        self._run()

        self.assertFalse(
            FounderAccount.objects.filter(
                handle__iexact="dj"
            ).exists()
        )

    def test_second_run_is_idempotent(self):
        self._run()

        founder_count = FounderAccount.objects.count()
        listing_count = FounderListing.objects.count()

        self._run()

        self.assertEqual(
            FounderAccount.objects.count(),
            founder_count,
        )
        self.assertEqual(
            FounderListing.objects.count(),
            listing_count,
        )

        self.assertEqual(
            FounderListing.objects.filter(
                founder_account__handle__iexact="lya",
                status=FounderListing.STATUS_ACTIVE,
            ).count(),
            1,
        )

        self.luna_listing.refresh_from_db()

        self.assertEqual(
            self.luna_listing.fixed_price_credits,
            5_000,
        )
