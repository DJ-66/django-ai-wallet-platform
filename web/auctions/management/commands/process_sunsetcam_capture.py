import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from auctions.forms import FeedPostForm
from auctions.hashtags import sync_post_hashtags
from auctions.models import (
    FeedPostMedia,
    FeedPostTranslation,
    SunsetCamCapture,
)


CAPTURE_COPY = {
    "midnight": {
        "en": (
            "Midnight on the Paraná",
            """🌙 Midnight on the Paraná in Encarnación. ❤️

#SunsetCam #MidnightCam #Encarnacion #ParanaRiver #Paraguay #NightView #LiveSunsetCam""",
        ),
        "es": (
            "Medianoche sobre el Paraná",
            """🌙 Medianoche sobre el Paraná en Encarnación. ❤️

#SunsetCam #Medianoche #Encarnacion #RioParana #Paraguay #VistaNocturna #LiveSunsetCam""",
        ),
        "pt": (
            "Meia-noite sobre o Paraná",
            """🌙 Meia-noite sobre o Paraná em Encarnación. ❤️

#SunsetCam #MeiaNoite #Encarnacion #RioParana #Paraguai #VistaNoturna #LiveSunsetCam""",
        ),
    },

    "morning": {
        "en": (
            "Morning on the Paraná",
            """🌄 Morning light over the Paraná in Encarnación. ❤️

#SunsetCam #MorningCam #Encarnacion #ParanaRiver #Paraguay #MorningView #LiveSunsetCam""",
        ),
        "es": (
            "Mañana sobre el Paraná",
            """🌄 Luz de la mañana sobre el Paraná en Encarnación. ❤️

#SunsetCam #MananaPY #Encarnacion #RioParana #Paraguay #VistaMatutina #LiveSunsetCam""",
        ),
        "pt": (
            "Manhã sobre o Paraná",
            """🌄 Luz da manhã sobre o Paraná em Encarnación. ❤️

#SunsetCam #ManhaPY #Encarnacion #RioParana #Paraguai #VistaDaManha #LiveSunsetCam""",
        ),
    },

    "midday": {
        "en": (
            "Midday on the Paraná",
            """☀️ Midday on the Paraná in Encarnación. ❤️

#SunsetCam #MiddayCam #Encarnacion #ParanaRiver #Paraguay #DayView #LiveSunsetCam""",
        ),
        "es": (
            "Mediodía sobre el Paraná",
            """☀️ Mediodía sobre el Paraná en Encarnación. ❤️

#SunsetCam #MediodiaPY #Encarnacion #RioParana #Paraguay #VistaDelDia #LiveSunsetCam""",
        ),
        "pt": (
            "Meio-dia sobre o Paraná",
            """☀️ Meio-dia sobre o Paraná em Encarnación. ❤️

#SunsetCam #MeioDiaPY #Encarnacion #RioParana #Paraguai #VistaDoDia #LiveSunsetCam""",
        ),
    },

    "sunset": {
        "en": (
            "Tonight over the Paraná",
            """🌅 Encarnación settling into the evening. ❤️

#SunsetCam #PYSunset #Encarnacion #ParanaRiver #Paraguay #Sunset #LiveSunsetCam""",
        ),
        "es": (
            "Atardecer de hoy sobre el Paraná",
            """🌅 Encarnación entrando en la noche. ❤️

#SunsetCam #AtardecerPY #Encarnacion #RioParana #Paraguay #Atardecer #LiveSunsetCam""",
        ),
        "pt": (
            "Pôr do sol de hoje sobre o Paraná",
            """🌅 Encarnación entrando na noite. ❤️

#SunsetCam #PorDoSolPY #Encarnacion #RioParana #Paraguai #PorDoSol #LiveSunsetCam""",
        ),
    },
}

# The evening sequence uses the same multilingual sunset copy.
# The capture identity remains distinct so each frame can post
# exactly once per local date.
for _sunset_capture_type in (
    SunsetCamCapture.CAPTURE_SUNSET_1,
    SunsetCamCapture.CAPTURE_SUNSET_2,
    SunsetCamCapture.CAPTURE_SUNSET_3,
    SunsetCamCapture.CAPTURE_SUNSET_4,
):
    CAPTURE_COPY[_sunset_capture_type] = (
        CAPTURE_COPY[SunsetCamCapture.CAPTURE_SUNSET]
    )


class Command(BaseCommand):
    help = (
        "Capture and publish scheduled @SunsetCam still images."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without capturing or posting.",
        )

        parser.add_argument(
            "--force",
            choices=[
                SunsetCamCapture.CAPTURE_MIDNIGHT,
                SunsetCamCapture.CAPTURE_MORNING,
                SunsetCamCapture.CAPTURE_MIDDAY,
                SunsetCamCapture.CAPTURE_SUNSET,
                SunsetCamCapture.CAPTURE_SUNSET_1,
                SunsetCamCapture.CAPTURE_SUNSET_2,
                SunsetCamCapture.CAPTURE_SUNSET_3,
                SunsetCamCapture.CAPTURE_SUNSET_4,
            ],
            help="Force one capture type regardless of the current time.",
        )

    def _get_timezone(self):
        timezone_name = os.environ.get(
            "SUNSETCAM_TIMEZONE",
            "America/Asuncion",
        ).strip()

        try:
            return ZoneInfo(timezone_name)
        except Exception as exc:
            raise CommandError(
                f"Invalid SUNSETCAM_TIMEZONE: {timezone_name}"
            ) from exc

    def _get_today_solar_times(self, now_local):
        latitude = os.environ.get(
            "SUNSETCAM_LATITUDE",
            "",
        ).strip()

        longitude = os.environ.get(
            "SUNSETCAM_LONGITUDE",
            "",
        ).strip()

        timezone_name = os.environ.get(
            "SUNSETCAM_TIMEZONE",
            "America/Asuncion",
        ).strip()

        if not latitude or not longitude:
            raise CommandError(
                "SUNSETCAM_LATITUDE and "
                "SUNSETCAM_LONGITUDE are required."
            )

        try:
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "daily": "sunrise,sunset",
                    "forecast_days": 1,
                    "timezone": timezone_name,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except (
            requests.RequestException,
            ValueError,
        ) as exc:
            raise CommandError(
                "Unable to retrieve SunsetCam solar times."
            ) from exc

        daily = data.get("daily") or {}

        sunrises = daily.get("sunrise") or []
        sunsets = daily.get("sunset") or []

        if not sunrises or not sunsets:
            raise CommandError(
                "Open-Meteo returned incomplete solar times."
            )

        sunrise_naive = datetime.fromisoformat(
            sunrises[0]
        )
        sunset_naive = datetime.fromisoformat(
            sunsets[0]
        )

        return (
            sunrise_naive.replace(
                tzinfo=now_local.tzinfo
            ),
            sunset_naive.replace(
                tzinfo=now_local.tzinfo
            ),
        )

    def _due_capture_type(self, now_local):
        minute_of_day = (
            now_local.hour * 60
            + now_local.minute
        )

        fixed_slots = {
            SunsetCamCapture.CAPTURE_MIDNIGHT:
                0,
            SunsetCamCapture.CAPTURE_MIDDAY:
                12 * 60,
            SunsetCamCapture.CAPTURE_SUNSET_1:
                18 * 60 + 5,
            SunsetCamCapture.CAPTURE_SUNSET_2:
                18 * 60 + 15,
            SunsetCamCapture.CAPTURE_SUNSET_3:
                18 * 60 + 25,
        }

        for (
            capture_type,
            target_minute,
        ) in fixed_slots.items():
            if (
                target_minute
                <= minute_of_day
                <= target_minute + 4
            ):
                return capture_type

        # Morning follows the seasons instead of using a
        # fixed 06:00 slot. Five minutes after sunrise gives
        # the camera useful daylight while staying close to
        # the start of the day.
        if 4 <= now_local.hour <= 10:
            sunrise, _ = (
                self._get_today_solar_times(
                    now_local
                )
            )

            morning_target = (
                sunrise
                + timedelta(minutes=5)
            )

            if (
                morning_target
                <= now_local
                <= morning_target
                + timedelta(minutes=4)
            ):
                return (
                    SunsetCamCapture.
                    CAPTURE_MORNING
                )

        # Final evening frame follows astronomical sunset.
        if 16 <= now_local.hour <= 21:
            _, sunset = (
                self._get_today_solar_times(
                    now_local
                )
            )

            if (
                sunset
                <= now_local
                <= sunset
                + timedelta(minutes=4)
            ):
                return (
                    SunsetCamCapture.
                    CAPTURE_SUNSET_4
                )

        return None

    def _capture_frame(self):
        rtsp_url = os.environ.get(
            "SUNSETCAM_RTSP_URL",
            "",
        ).strip()

        if not rtsp_url:
            raise CommandError(
                "SUNSETCAM_RTSP_URL is not configured."
            )

        temp_file = tempfile.NamedTemporaryFile(
            prefix="sunsetcam-",
            suffix=".jpg",
            delete=False,
        )
        temp_file.close()

        output_path = Path(temp_file.name)

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-rtsp_transport",
            "tcp",
            "-i",
            rtsp_url,
            "-frames:v",
            "1",
            "-update",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            output_path.unlink(missing_ok=True)
            raise CommandError(
                "SunsetCam FFmpeg capture failed."
            ) from exc

        if result.returncode != 0:
            output_path.unlink(missing_ok=True)
            raise CommandError(
                "SunsetCam FFmpeg capture failed."
            )

        if (
            not output_path.exists()
            or output_path.stat().st_size == 0
        ):
            output_path.unlink(missing_ok=True)
            raise CommandError(
                "SunsetCam capture produced no image."
            )

        return output_path

    def _build_form(self, source_path, user, capture_type):
        title, content = CAPTURE_COPY[capture_type]["en"]

        with source_path.open("rb") as fh:
            upload = SimpleUploadedFile(
                f"sunsetcam-{capture_type}.jpg",
                fh.read(),
                content_type="image/jpeg",
            )

        form = FeedPostForm(
            data={
                "title": title,
                "content": content,
                "media_type": "image",
                "is_paid": False,
                "is_public": True,
                "unlock_price": 0,
            },
            files={
                "images": [upload],
            },
            current_username=user.username,
        )

        if not form.is_valid():
            raise CommandError(
                "SunsetCam FeedPostForm validation failed: "
                + form.errors.as_json()
            )

        return form

    def _create_post(
        self,
        *,
        now_local,
        capture_type,
        source_path,
    ):
        # Lock the SunsetCam user row so two concurrent workers cannot
        # publish the same slot at the same time.
        with transaction.atomic():
            user = (
                User.objects
                .select_for_update()
                .get(username__iexact="SunsetCam")
            )

            existing = (
                SunsetCamCapture.objects
                .filter(
                    local_date=now_local.date(),
                    capture_type=capture_type,
                )
                .first()
            )

            if existing:
                return existing.post, False

            form = self._build_form(
                source_path,
                user,
                capture_type,
            )

            post = form.save(commit=False)
            post.user = user
            post.title = post.title.strip()
            post.content = post.content.strip()
            post.is_public = True
            post.is_paid = False
            post.unlock_price = 0
            post.save()

            media_items = form.cleaned_data.get(
                "images",
                [],
            )

            for display_order, media_item in enumerate(media_items):
                FeedPostMedia.objects.create(
                    post=post,
                    file=media_item["file"],
                    media_type=media_item["media_type"],
                    caption="",
                    display_order=display_order,
                    is_active=True,
                )

            for language, (title, content) in (
                CAPTURE_COPY[capture_type].items()
            ):
                FeedPostTranslation.objects.update_or_create(
                    post=post,
                    language=language,
                    defaults={
                        "title": title,
                        "content": content,
                    },
                )

            sync_post_hashtags(post)

            SunsetCamCapture.objects.create(
                local_date=now_local.date(),
                capture_type=capture_type,
                post=post,
            )

            return post, True

    def handle(self, *args, **options):
        tz = self._get_timezone()
        now_local = datetime.now(tz)

        capture_type = (
            options.get("force")
            or self._due_capture_type(now_local)
        )

        self.stdout.write(
            f"sunsetcam_local_time={now_local.isoformat()}"
        )

        if not capture_type:
            self.stdout.write("sunsetcam_due=none")
            return

        already_exists = (
            SunsetCamCapture.objects
            .filter(
                local_date=now_local.date(),
                capture_type=capture_type,
            )
            .exists()
        )

        self.stdout.write(
            f"sunsetcam_due={capture_type}"
        )
        self.stdout.write(
            "sunsetcam_already_posted="
            + str(already_exists).lower()
        )

        if already_exists:
            return

        if options.get("dry_run"):
            self.stdout.write(
                "sunsetcam_action=would_capture_and_post"
            )
            return

        source_path = None

        try:
            source_path = self._capture_frame()

            post, created = self._create_post(
                now_local=now_local,
                capture_type=capture_type,
                source_path=source_path,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "sunsetcam_post="
                    f"{post.pk} "
                    f"capture_type={capture_type} "
                    f"created={str(created).lower()}"
                )
            )
        finally:
            if source_path:
                source_path.unlink(missing_ok=True)
