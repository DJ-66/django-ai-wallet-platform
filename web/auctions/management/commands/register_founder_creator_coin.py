from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from auctions.models import (
    EconomyAsset,
    FounderAccount,
)
from auctions.validators import (
    FOUNDER_FLOOR_CREDITS,
    validate_founder_handle,
)


GENESIS_SUPPLY_BASE_UNITS = 21_000_000_000_000_000
DECIMALS = 6


class Command(BaseCommand):
    help = (
        "Register an already-generated fixed-supply "
        "Sui creator coin with a FANZ Founder Account."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "handle",
            help="Founder handle, with or without @.",
        )

        parser.add_argument(
            "--symbol",
            required=True,
        )

        parser.add_argument(
            "--name",
            required=True,
        )

        parser.add_argument(
            "--package-name",
            required=True,
            help=(
                "Generated Sui package name, for example "
                "fanz_creator_lisa."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        handle = validate_founder_handle(
            options["handle"]
        )

        symbol = options["symbol"].strip()
        name = options["name"].strip()
        package_name = (
            options["package_name"].strip()
        )

        if not symbol:
            raise CommandError(
                "Creator coin symbol cannot be empty."
            )

        if not name:
            raise CommandError(
                "Creator coin name cannot be empty."
            )

        if not package_name:
            raise CommandError(
                "Package name cannot be empty."
            )

        founder, founder_created = (
            FounderAccount.objects.get_or_create(
                handle=handle,
                defaults={
                    "status":
                        FounderAccount.STATUS_AVAILABLE,
                    "floor_price_credits":
                        FOUNDER_FLOOR_CREDITS,
                },
            )
        )

        founder = (
            FounderAccount.objects
            .select_for_update()
            .get(pk=founder.pk)
        )

        existing = EconomyAsset.objects.filter(
            founder_account=founder
        ).first()

        if existing is not None:
            raise CommandError(
                f"@{handle} already has EconomyAsset "
                f"id={existing.pk}."
            )

        asset = EconomyAsset.objects.create(
            founder_account=founder,
            name=name,
            symbol=symbol,
            chain="sui",
            decimals=DECIMALS,
            genesis_supply_base_units=(
                GENESIS_SUPPLY_BASE_UNITS
            ),
            status=EconomyAsset.STATUS_DRAFT,
            metadata={
                "generated_package":
                    package_name,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Registered @{handle} creator coin."
            )
        )

        self.stdout.write(
            f"founder_created={founder_created}"
        )
        self.stdout.write(
            f"founder_account_id={founder.pk}"
        )
        self.stdout.write(
            f"economy_asset_id={asset.pk}"
        )
        self.stdout.write(
            f"generated_package={package_name}"
        )
