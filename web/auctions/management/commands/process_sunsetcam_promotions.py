"""Schedule capture-dependent SunsetCam promotions."""

import os
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from auctions.management.commands.process_sunsetcam_capture import (
    Command as CaptureCommand,
)
from auctions.sunsetcam_promotional_scheduling import (
    PREPARATION_WINDOW,
    PROMOTIONAL_SLOTS,
    promotional_slot_time,
    schedule_sunsetcam_promotion,
)
from auctions.models import SunsetCamCapture, UserProfile


User = get_user_model()

ENABLED_VALUES = {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "Schedule approved SunsetCam promotions after captures."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):
        enabled = (
            os.environ.get(
                "FANZ_SUNSETCAM_PROMOTIONS_ENABLED",
                "false",
            ).strip().lower()
            in ENABLED_VALUES
        )

        dry_run = options["dry_run"]

        if not enabled and not dry_run:
            self.stdout.write(
                "sunsetcam_promotions=disabled"
            )
            return

        capture_command = CaptureCommand()
        tz = capture_command._get_timezone()
        now = datetime.now(tz)
        local_date = now.date()

        account = User.objects.filter(
            username__iexact="SunsetCam",
        ).first()

        if account is None:
            raise CommandError("SunsetCam account not found.")

        if not UserProfile.objects.filter(
            user=account,
            is_platform_account=True,
        ).exists():
            raise CommandError(
                "SunsetCam is not an authorized platform account."
            )

        referral_code = os.environ.get(
            "FANZ_SUNSETCAM_REFERRAL_CODE",
            "",
        ).strip()

        if not referral_code:
            raise CommandError(
                "SunsetCam referral code is not configured."
            )

        referral_url = (
            "https://fanz.to/auctions/signup/"
            f"?ref={referral_code}"
        )

        # Solar lookup is needed only for the sunset slot.
        sunset = None

        for slot, capture_type in PROMOTIONAL_SLOTS.items():
            if slot == "sunset":
                # Avoid solar API calls outside the evening.
                # SunsetCam capture scheduling uses the same
                # 16:00–21:59 local-hour envelope.
                if not 16 <= now.hour <= 21:
                    continue

                _, sunset = (
                    capture_command._get_today_solar_times(now)
                )

            try:
                target = promotional_slot_time(
                    local_date=local_date,
                    slot=slot,
                    timezone_name=str(tz),
                    sunset=sunset,
                )
            except ValidationError as exc:
                raise CommandError(str(exc)) from exc

            if not (
                target - PREPARATION_WINDOW
                <= now
                < target
            ):
                continue

            capture_exists = SunsetCamCapture.objects.filter(
                local_date=local_date,
                capture_type=capture_type,
                post__user=account,
            ).exists()

            if not capture_exists:
                self.stdout.write(
                    f"slot={slot} action=capture_missing"
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"slot={slot} action=would_schedule "
                    f"scheduled_for={target.isoformat()}"
                )
                continue

            try:
                publication, created, reason = (
                    schedule_sunsetcam_promotion(
                        account=account,
                        local_date=local_date,
                        slot=slot,
                        referral_url=referral_url,
                        now=now,
                        sunset=sunset,
                        timezone_name=str(tz),
                    )
                )
            except ValidationError as exc:
                raise CommandError(str(exc)) from exc

            self.stdout.write(
                f"slot={slot} action={reason} "
                f"publication_id="
                f"{publication.pk if publication else 'none'} "
                f"created={str(created).lower()}"
            )
