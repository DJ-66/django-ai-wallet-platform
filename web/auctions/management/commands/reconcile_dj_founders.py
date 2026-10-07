from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from auctions.founder_services import get_authoritative_root
from auctions.models import FounderAccount, FounderListing
from auctions.validators import (
    FOUNDER_FLOOR_CREDITS,
    is_valid_founder_handle,
)


PROTECTED_HANDLES = frozenset({
    "dj",
})


class Command(BaseCommand):
    help = (
        "Reconcile active 3-4 character FANZ accounts into "
        "DJ-owned Founder properties. Existing ownership and "
        "active listings are preserved."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            default="DJ",
        )
        parser.add_argument(
            "--price",
            type=int,
            default=100_000,
            help=(
                "Initial fixed P2P asking price for Founder "
                "properties that do not already have an "
                "active listing."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        owner_name = options["owner"]
        initial_price = int(options["price"])
        dry_run = bool(options["dry_run"])

        if initial_price < FOUNDER_FLOOR_CREDITS:
            raise CommandError(
                f"Initial price must be at least "
                f"{FOUNDER_FLOOR_CREDITS} credits."
            )

        try:
            owner = User.objects.get(
                username__iexact=owner_name
            )
        except User.DoesNotExist as exc:
            raise CommandError(
                f"Owner @{owner_name} does not exist."
            ) from exc

        owner_root = get_authoritative_root(owner)

        users = []

        for user in User.objects.filter(
            is_active=True
        ).order_by("username"):
            raw = (user.username or "").strip()

            if not (3 <= len(raw) <= 4):
                continue

            if not is_valid_founder_handle(raw):
                continue

            if raw.casefold() in PROTECTED_HANDLES:
                continue

            users.append(user)

        counts = {
            "eligible": len(users),
            "missing_founder": 0,
            "unowned_existing": 0,
            "owned_by_target": 0,
            "other_owner": 0,
            "would_create": 0,
            "would_assign": 0,
            "would_link": 0,
            "would_list": 0,
            "existing_active_listing": 0,
            "current_account_conflict": 0,
        }

        plans = []

        for user in users:
            founder = (
                FounderAccount.objects
                .filter(
                    handle__iexact=user.username
                )
                .select_related(
                    "owner_root",
                    "current_account",
                )
                .first()
            )

            actions = []

            if founder is None:
                counts["missing_founder"] += 1
                counts["would_create"] += 1
                counts["would_assign"] += 1
                counts["would_link"] += 1
                counts["would_list"] += 1

                actions = [
                    "CREATE",
                    f"OWNER=@{owner_root.username}",
                    f"CURRENT=@{user.username}",
                    f"LIST-P2P={initial_price}",
                ]

            elif (
                founder.owner_root_id is not None
                and founder.owner_root_id != owner_root.pk
            ):
                counts["other_owner"] += 1

                actions = [
                    "PRESERVE-OTHER-OWNER",
                ]

            else:
                if founder.owner_root_id is None:
                    counts["unowned_existing"] += 1
                    counts["would_assign"] += 1
                    actions.append(
                        f"OWNER=@{owner_root.username}"
                    )
                else:
                    counts["owned_by_target"] += 1

                if founder.current_account_id is None:
                    counts["would_link"] += 1
                    actions.append(
                        f"CURRENT=@{user.username}"
                    )

                elif founder.current_account_id != user.pk:
                    counts["current_account_conflict"] += 1
                    actions.append(
                        "PRESERVE-CURRENT-CONFLICT"
                    )

                active = (
                    FounderListing.objects
                    .filter(
                        founder_account=founder,
                        status=FounderListing.STATUS_ACTIVE,
                    )
                    .select_related("seller_root")
                    .first()
                )

                if active is not None:
                    counts["existing_active_listing"] += 1

                    actions.append(
                        "PRESERVE-LISTING"
                        f"#{active.pk}"
                        f":{active.listing_source}"
                        f":{active.sale_type}"
                        f":{active.fixed_price_credits}"
                    )
                else:
                    counts["would_list"] += 1
                    actions.append(
                        f"LIST-P2P={initial_price}"
                    )

                if not actions:
                    actions.append("NO-CHANGE")

            plans.append(
                (user, founder, actions)
            )

        self.stdout.write(
            f"Owner: @{owner_root.username}"
        )
        self.stdout.write(
            f"Initial P2P price: "
            f"{initial_price:,} credits"
        )
        self.stdout.write(
            "Mode: "
            + ("DRY RUN" if dry_run else "EXECUTE")
        )
        self.stdout.write("")

        for user, founder, actions in plans:
            existing_owner = (
                founder.owner_root.username
                if founder and founder.owner_root
                else "-"
            )

            self.stdout.write(
                f"@{user.username}: "
                f"founder="
                f"{founder.handle if founder else '-'} "
                f"owner={existing_owner} "
                f"-> {', '.join(actions)}"
            )

        self.stdout.write("")

        for key, value in counts.items():
            self.stdout.write(
                f"{key}: {value}"
            )

        if dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    "DRY RUN COMPLETE: "
                    "no database changes made."
                )
            )
            return

        with transaction.atomic():
            for user, founder, actions in plans:
                if "PRESERVE-OTHER-OWNER" in actions:
                    continue

                if founder is None:
                    founder = FounderAccount.objects.create(
                        handle=user.username,
                        owner_root=owner_root,
                        current_account=user,
                        status=FounderAccount.STATUS_OWNED,
                        floor_price_credits=(
                            FOUNDER_FLOOR_CREDITS
                        ),
                    )

                else:
                    # Lock only the Founder row. current_account
                    # is nullable, so do not select_related() it
                    # together with SELECT FOR UPDATE.
                    founder = (
                        FounderAccount.objects
                        .select_for_update()
                        .get(pk=founder.pk)
                    )

                    changed = []

                    if founder.owner_root_id is None:
                        founder.owner_root = owner_root
                        changed.append("owner_root")

                    if founder.current_account_id is None:
                        founder.current_account = user
                        changed.append("current_account")

                    if changed:
                        changed.append("updated_at")
                        founder.save(
                            update_fields=changed
                        )

                active = (
                    FounderListing.objects
                    .select_for_update()
                    .filter(
                        founder_account=founder,
                        status=FounderListing.STATUS_ACTIVE,
                    )
                    .first()
                )

                # Existing market decisions are authoritative.
                # Never reprice or replace an active listing.
                if active is not None:
                    continue

                FounderListing.objects.create(
                    founder_account=founder,
                    seller_root=owner_root,
                    listing_source=FounderListing.SOURCE_P2P,
                    tienda_lane=None,
                    sale_type=FounderListing.SALE_FIXED,
                    fixed_price_credits=initial_price,
                    status=FounderListing.STATUS_ACTIVE,
                )

                founder.status = FounderAccount.STATUS_LISTED
                founder.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "DJ Founder reconciliation complete."
            )
        )
