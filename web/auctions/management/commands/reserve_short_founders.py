from itertools import product

from django.contrib.auth import get_user_model
from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from auctions.models import FounderAccount, FounderListing
from auctions.validators import (
    FOUNDER_ALLOWED_CHARS,
    validate_founder_handle,
)


DEFAULT_PRICE = 100_000


def iter_short_handles():
    alphabet = sorted(FOUNDER_ALLOWED_CHARS)

    for length in (1, 2):
        for chars in product(alphabet, repeat=length):
            handle = "".join(chars)
            yield validate_founder_handle(handle)


class Command(BaseCommand):
    help = (
        "Reserve every valid 1-2 character Founder property "
        "for an existing owner account."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            required=True,
            help="Existing FANZ username that will own the properties.",
        )
        parser.add_argument(
            "--price",
            type=int,
            default=DEFAULT_PRICE,
            help="Default fixed listing price in FANZ credits.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report actions without changing the database.",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        owner_name = options["owner"].strip()
        price = int(options["price"])
        dry_run = bool(options["dry_run"])

        if price < 200:
            raise CommandError(
                "Founder listing price must be at least 200 credits."
            )

        owner = (
            User.objects
            .filter(
                username__iexact=owner_name,
                is_active=True,
            )
            .first()
        )

        if owner is None:
            raise CommandError(
                f"Active owner @{owner_name} does not exist."
            )

        handles = list(iter_short_handles())

        counts = {
            "namespace": len(handles),
            "missing": 0,
            "owned_by_target": 0,
            "other_owner": 0,
            "unowned_existing": 0,
            "active_listing": 0,
            "would_create": 0,
            "would_assign": 0,
            "would_list": 0,
        }

        conflicts = []

        for handle in handles:
            founder = (
                FounderAccount.objects
                .select_related("owner_root")
                .filter(handle__iexact=handle)
                .first()
            )

            if founder is None:
                counts["missing"] += 1
                counts["would_create"] += 1
                counts["would_assign"] += 1
                counts["would_list"] += 1
                continue

            if founder.owner_root_id == owner.pk:
                counts["owned_by_target"] += 1
            elif founder.owner_root_id is None:
                counts["unowned_existing"] += 1
                counts["would_assign"] += 1
            else:
                counts["other_owner"] += 1
                conflicts.append(
                    (
                        handle,
                        founder.owner_root.username,
                        founder.status,
                    )
                )
                continue

            has_listing = FounderListing.objects.filter(
                founder_account=founder,
                status=FounderListing.STATUS_ACTIVE,
            ).exists()

            if has_listing:
                counts["active_listing"] += 1
            else:
                counts["would_list"] += 1

        self.stdout.write(
            f"Target owner: @{owner.username}"
        )
        self.stdout.write(
            f"Price: {price:,} FANZ credits"
        )
        self.stdout.write(
            f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}"
        )
        self.stdout.write("")

        for key in (
            "namespace",
            "missing",
            "owned_by_target",
            "unowned_existing",
            "other_owner",
            "active_listing",
            "would_create",
            "would_assign",
            "would_list",
        ):
            self.stdout.write(
                f"{key}: {counts[key]}"
            )

        if conflicts:
            self.stdout.write("")
            self.stdout.write(
                "Existing other-owner assets preserved:"
            )
            for handle, existing_owner, status in conflicts:
                self.stdout.write(
                    f"  @{handle}: owner=@{existing_owner} "
                    f"status={status}"
                )

        if dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    "DRY RUN COMPLETE: no database changes made."
                )
            )
            return

        from django.db import transaction

        from auctions.founder_services import (
            get_authoritative_root,
        )
        from auctions.validators import FOUNDER_FLOOR_CREDITS

        owner_root = get_authoritative_root(owner)

        created_count = 0
        assigned_count = 0
        listed_count = 0
        preserved_count = 0

        with transaction.atomic():
            for handle in handles:
                founder = (
                    FounderAccount.objects
                    .select_for_update()
                    .filter(handle__iexact=handle)
                    .first()
                )

                if founder is None:
                    founder = FounderAccount.objects.create(
                        handle=handle,
                        owner_root=owner_root,
                        status=FounderAccount.STATUS_TREASURY,
                        floor_price_credits=FOUNDER_FLOOR_CREDITS,
                    )
                    created_count += 1
                    assigned_count += 1

                elif (
                    founder.owner_root_id is not None
                    and founder.owner_root_id != owner_root.pk
                ):
                    preserved_count += 1
                    continue

                else:
                    changed_fields = []

                    if founder.owner_root_id is None:
                        founder.owner_root = owner_root
                        assigned_count += 1
                        changed_fields.append("owner_root")

                    active_listing = (
                        FounderListing.objects
                        .filter(
                            founder_account=founder,
                            status=FounderListing.STATUS_ACTIVE,
                        )
                        .first()
                    )

                    if active_listing is not None:
                        preserved_count += 1

                        if changed_fields:
                            changed_fields.append("updated_at")
                            founder.save(
                                update_fields=changed_fields
                            )

                        continue

                    if founder.status != FounderAccount.STATUS_TREASURY:
                        founder.status = FounderAccount.STATUS_TREASURY
                        changed_fields.append("status")

                    if founder.floor_price_credits < FOUNDER_FLOOR_CREDITS:
                        founder.floor_price_credits = FOUNDER_FLOOR_CREDITS
                        changed_fields.append("floor_price_credits")

                    if changed_fields:
                        changed_fields.append("updated_at")
                        founder.save(
                            update_fields=changed_fields
                        )

                active_listing = (
                    FounderListing.objects
                    .filter(
                        founder_account=founder,
                        status=FounderListing.STATUS_ACTIVE,
                    )
                    .first()
                )

                if active_listing is not None:
                    preserved_count += 1
                    continue

                FounderListing.objects.create(
                    founder_account=founder,
                    seller_root=owner_root,
                    listing_source=FounderListing.SOURCE_TIENDA,
                    tienda_lane=FounderListing.TIENDA_FIXED,
                    sale_type=FounderListing.SALE_FIXED,
                    fixed_price_credits=price,
                    status=FounderListing.STATUS_ACTIVE,
                )

                founder.status = FounderAccount.STATUS_LISTED
                founder.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                listed_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Short Founder reservation complete."
            )
        )
        self.stdout.write(f"created: {created_count}")
        self.stdout.write(f"assigned: {assigned_count}")
        self.stdout.write(f"listed: {listed_count}")
        self.stdout.write(f"preserved: {preserved_count}")
