"""Manually schedule approved FANZ promotional campaigns."""

from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auctions.models import UserProfile
from auctions.promotional_overlays import _validate_referral_url
from auctions.promotional_rotation import select_promotional_rotation
from auctions.promotional_scheduling import (
    schedule_promotional_publication,
)


User = get_user_model()


class Command(BaseCommand):
    help = "Preview or queue a platform-owned promotional campaign."

    def add_arguments(self, parser):
        parser.add_argument("--account", required=True)
        parser.add_argument(
            "--days-ahead",
            type=int,
            required=True,
        )
        parser.add_argument(
            "--referral-code",
            required=True,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):
        if options["days_ahead"] < 1:
            raise CommandError(
                "--days-ahead must be at least 1."
            )

        account = User.objects.filter(
            username__iexact=options["account"],
        ).first()

        if account is None:
            raise CommandError("Account not found.")

        if not UserProfile.objects.filter(
            user=account,
            is_platform_account=True,
        ).exists():
            raise CommandError(
                "Account is not a FANZ platform account."
            )

        referral_url = (
            "https://fanz.to/auctions/signup/"
            f"?ref={options['referral_code']}"
        )

        try:
            _validate_referral_url(referral_url)
        except ValueError as exc:
            raise CommandError(
                "Invalid FANZ referral code."
            ) from exc

        target_date = (
            timezone.now().astimezone(dt_timezone.utc).date()
            + timedelta(days=options["days_ahead"])
        )

        scheduled_for = datetime.combine(
            target_date,
            time(hour=12),
            tzinfo=dt_timezone.utc,
        )

        if options["dry_run"]:
            try:
                selection = select_promotional_rotation(account)
            except ValidationError as exc:
                raise CommandError(str(exc)) from exc

            self.stdout.write(
                f"account=@{account.username}"
            )
            self.stdout.write(
                f"campaign={selection.campaign_key}"
            )
            self.stdout.write(
                f"media_asset_id={selection.media_asset_id}"
            )
            self.stdout.write(
                f"scheduled_for={scheduled_for.isoformat()}"
            )
            self.stdout.write(
                "action=would_schedule"
            )
            return

        try:
            publication, created = (
                schedule_promotional_publication(
                    account=account,
                    scheduled_for=scheduled_for,
                    referral_url=referral_url,
                )
            )
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"publication_id={publication.pk}"
        )
        self.stdout.write(
            f"publication_key={publication.publication_key}"
        )
        self.stdout.write(
            f"campaign={publication.campaign_key}"
        )
        self.stdout.write(
            f"media_asset_id={publication.media_asset_id}"
        )
        self.stdout.write(
            f"status={publication.status}"
        )
        self.stdout.write(
            f"created={str(created).lower()}"
        )
