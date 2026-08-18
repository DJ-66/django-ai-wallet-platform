from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from auctions.founder_tienda import replenish_founder_tienda
from auctions.models import FounderAccount, FounderListing
from auctions.utils import get_system_wallet


PREMIUM_HANDLES = [
    "dogs",
    "cats",
    "wolf",
    "alex",
    "love",
    "cash",
    "777",
    "box",
    "gold",
    "star",
]

BLIND_HANDLES = [
    "cars",
    "cool",
    "hot",
    "vip",
    "max",
    "lux",
    "fun",
    "hero",
    "moon",
    "meta",
]

WASTELAND_HANDLES = [
    "q7_+",
    "9_z-",
    "x0_q",
    "_7x+",
    "q-9_",
    "z+0_",
    "8_q-",
    "x_3+",
    "7-z_",
    "q0_-",
]


PREMIUM_RESERVE_HANDLES = [
    "blue",
    "club",
    "game",
    "king",
    "rock",
]

BLIND_RESERVE_HANDLES = [
    "nova",
    "zone",
    "wild",
    "wave",
    "fire",
]

WASTELAND_RESERVE_HANDLES = [
    "z9_-",
    "q8_+",
    "x4_-",
    "7_q+",
    "_9z-",
]

class Command(BaseCommand):
    help = (
        "Ensure curated FANZ Founder Tienda Treasury inventory exists "
        "and replenish active lanes toward 10 fixed / 10 blind / "
        "10 Wasteland listings."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        platform_wallet = get_system_wallet()
        platform_user = platform_wallet.user

        curated = (
            PREMIUM_HANDLES
            + BLIND_HANDLES
            + WASTELAND_HANDLES
            + PREMIUM_RESERVE_HANDLES
            + BLIND_RESERVE_HANDLES
            + WASTELAND_RESERVE_HANDLES
        )

        if len(curated) != len(set(curated)):
            raise CommandError(
                "Duplicate handle exists in curated Tienda configuration."
            )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "FANZ Founder Tienda"
            )
        )

        created_assets = 0
        existing_assets = 0

        for handle in curated:
            # Do not silently seize a username already used by a
            # non-platform Django account.
            existing_user = (
                User.objects
                .filter(username__iexact=handle)
                .exclude(pk=platform_user.pk)
                .first()
            )

            if existing_user is not None:
                raise CommandError(
                    f"Cannot seed @{handle}: Django user "
                    f"@{existing_user.username} already exists."
                )

            asset, created = FounderAccount.objects.get_or_create(
                handle=handle,
                defaults={
                    "owner_root": platform_user,
                    "status": FounderAccount.STATUS_TREASURY,
                    "floor_price_credits": 200,
                },
            )

            if created:
                created_assets += 1

                self.stdout.write(
                    f"Created Treasury parcel @{asset.handle}"
                )

                continue

            existing_assets += 1

            # Existing private property must never be pulled back
            # into Treasury by a replenishment command.
            if (
                asset.owner_root_id is not None
                and asset.owner_root_id != platform_user.pk
            ):
                self.stdout.write(
                    self.style.WARNING(
                    f"Skipping @{handle}: privately owned by "
                    f"@{asset.owner_root.username}."
                )
            )
            continue

            # If the asset already has a live listing, leave its
            # listing/state untouched.
            has_active_listing = FounderListing.objects.filter(
                founder_account=asset,
                status=FounderListing.STATUS_ACTIVE,
            ).exists()

            if not has_active_listing:
                asset.owner_root = platform_user
                asset.status = FounderAccount.STATUS_TREASURY

                if asset.floor_price_credits < 200:
                    asset.floor_price_credits = 200

                asset.save(
                    update_fields=[
                        "owner_root",
                        "status",
                        "floor_price_credits",
                        "updated_at",
                    ]
                )
        def eligible_handles(handles):
            return list(
                FounderAccount.objects
                .filter(
                    handle__in=handles,
                    owner_root=platform_user,
                    status__in=[
                        FounderAccount.STATUS_AVAILABLE,
                        FounderAccount.STATUS_TREASURY,
                    ],
                )
                .exclude(
                    listings__status=FounderListing.STATUS_ACTIVE,
                )
                .values_list(
                    "handle",
                    flat=True,
                )
            )

        fixed_candidates = eligible_handles(
            PREMIUM_HANDLES
            + PREMIUM_RESERVE_HANDLES
        )

        blind_candidates = eligible_handles(
            BLIND_HANDLES
            + BLIND_RESERVE_HANDLES
        )

        wasteland_candidates = eligible_handles(
            WASTELAND_HANDLES
            + WASTELAND_RESERVE_HANDLES
        )

        result = replenish_founder_tienda(
            fixed_handles=fixed_candidates,
            blind_handles=blind_candidates,
            swamp_handles=wasteland_candidates,
        )

        fixed_count = FounderListing.objects.filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_FIXED,
            status=FounderListing.STATUS_ACTIVE,
        ).count()

        blind_count = FounderListing.objects.filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_BLIND,
            status=FounderListing.STATUS_ACTIVE,
        ).count()

        wasteland_count = FounderListing.objects.filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_SWAMP,
            status=FounderListing.STATUS_ACTIVE,
        ).count()

        total_count = (
            fixed_count
            + blind_count
            + wasteland_count
        )

        self.stdout.write("")
        self.stdout.write(
            f"Founder parcels created: {created_assets}"
        )
        self.stdout.write(
            f"Founder parcels existing: {existing_assets}"
        )

        self.stdout.write("")
        self.stdout.write(
            f"Listings created this run: {result}"
        )

        self.stdout.write("")
        self.stdout.write(
            f"Premium / Fixed: {fixed_count}"
        )
        self.stdout.write(
            f"Blind Offer: {blind_count}"
        )
        self.stdout.write(
            f"The Wasteland: {wasteland_count}"
        )
        self.stdout.write(
            f"Total Tienda: {total_count}"
        )

        if (
            fixed_count != 10
            or blind_count != 10
            or wasteland_count != 10
            or total_count != 30
        ):
            raise CommandError(
                "Founder Tienda did not reach the expected "
                "10 / 10 / 10 inventory target."
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "FOUNDER TIENDA 10 / 10 / 10: READY"
            )
        )
