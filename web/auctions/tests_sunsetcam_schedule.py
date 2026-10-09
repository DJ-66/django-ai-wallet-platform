from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from auctions.management.commands.process_sunsetcam_capture import (
    Command,
)
from auctions.models import SunsetCamCapture


class SunsetCamScheduleTests(SimpleTestCase):
    def setUp(self):
        self.command = Command()
        self.tz = ZoneInfo("America/Asuncion")
        self.sunrise = datetime(
            2026, 10, 9, 6, 0, tzinfo=self.tz
        )
        self.sunset = datetime(
            2026, 10, 9, 18, 45, tzinfo=self.tz
        )

        self.solar_patch = patch.object(
            self.command,
            "_get_today_solar_times",
            return_value=(self.sunrise, self.sunset),
        )
        self.solar_patch.start()
        self.addCleanup(self.solar_patch.stop)

    def test_midnight_capture(self):
        now = self.sunrise.replace(hour=0, minute=0)
        self.assertEqual(
            self.command._due_capture_type(now),
            SunsetCamCapture.CAPTURE_MIDNIGHT,
        )

    def test_morning_capture(self):
        now = self.sunrise + timedelta(minutes=5)
        self.assertEqual(
            self.command._due_capture_type(now),
            SunsetCamCapture.CAPTURE_MORNING,
        )

    def test_midday_capture(self):
        now = self.sunrise.replace(hour=12, minute=0)
        self.assertEqual(
            self.command._due_capture_type(now),
            SunsetCamCapture.CAPTURE_MIDDAY,
        )

    def test_existing_evening_captures(self):
        for minute, capture_type in (
            (5, SunsetCamCapture.CAPTURE_SUNSET_1),
            (15, SunsetCamCapture.CAPTURE_SUNSET_2),
            (25, SunsetCamCapture.CAPTURE_SUNSET_3),
        ):
            with self.subTest(minute=minute):
                now = self.sunrise.replace(
                    hour=18,
                    minute=minute,
                )
                self.assertEqual(
                    self.command._due_capture_type(now),
                    capture_type,
                )

    def test_final_capture_five_minutes_before_sunset(self):
        now = self.sunset - timedelta(minutes=5)
        self.assertEqual(
            self.command._due_capture_type(now),
            SunsetCamCapture.CAPTURE_SUNSET_4,
        )

    def test_no_final_capture_at_sunset(self):
        self.assertIsNone(
            self.command._due_capture_type(self.sunset)
        )


class SunsetCamOverlapTests(SimpleTestCase):
    def setUp(self):
        self.command = Command()
        self.tz = ZoneInfo("America/Asuncion")

        self.sunrise = datetime(
            2026, 10, 9, 6, 0, tzinfo=self.tz
        )

        # Sunset -5 minutes overlaps the 18:25 fixed slot.
        self.sunset = datetime(
            2026, 10, 9, 18, 30, tzinfo=self.tz
        )

        self.solar_patch = patch.object(
            self.command,
            "_get_today_solar_times",
            return_value=(self.sunrise, self.sunset),
        )
        self.solar_patch.start()
        self.addCleanup(self.solar_patch.stop)

    def test_overlapping_capture_types_detected(self):
        now = self.sunset - timedelta(minutes=5)

        due = self.command._due_capture_types(now)

        self.assertIn(
            SunsetCamCapture.CAPTURE_SUNSET_3,
            due,
        )

        self.assertIn(
            SunsetCamCapture.CAPTURE_SUNSET_4,
            due,
        )

        self.assertEqual(len(due), 2)

    def test_legacy_single_capture_interface_preserved(self):
        now = self.sunset - timedelta(minutes=5)

        self.assertEqual(
            self.command._due_capture_type(now),
            SunsetCamCapture.CAPTURE_SUNSET_3,
        )


from io import StringIO
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from auctions.models import FeedPost


class SunsetCamCompletedSlotTests(TestCase):
    def test_completed_fixed_slot_does_not_block_solar_slot(self):
        tz = ZoneInfo("America/Asuncion")

        now = datetime(
            2026, 10, 9, 18, 25, tzinfo=tz
        )

        sunrise = now.replace(hour=6, minute=0)
        sunset = now.replace(hour=18, minute=30)

        User = get_user_model()
        user = User.objects.create_user(
            username="SunsetCam"
        )

        post = FeedPost.objects.create(
            user=user,
            title="Previously published capture",
            content="Test capture",
            is_public=True,
        )

        SunsetCamCapture.objects.create(
            local_date=now.date(),
            capture_type=SunsetCamCapture.CAPTURE_SUNSET_3,
            post=post,
        )

        command = Command()
        output = StringIO()
        command.stdout = output

        with (
            patch.object(
                command,
                "_get_timezone",
                return_value=tz,
            ),
            patch.object(
                command,
                "_get_today_solar_times",
                return_value=(sunrise, sunset),
            ),
            patch(
                "auctions.management.commands."
                "process_sunsetcam_capture.datetime"
            ) as mocked_datetime,
        ):
            mocked_datetime.now.return_value = now

            command.handle(
                force=None,
                dry_run=True,
            )

        # The fixed slot is completed, so the solar slot
        # must be selected instead.
        self.assertIn(
            "sunsetcam_due=sunset_4",
            output.getvalue(),
        )
        self.assertIn(
            "sunsetcam_action=would_capture_and_post",
            output.getvalue(),
        )
        self.assertTrue(
            SunsetCamCapture.objects.filter(
                local_date=now.date(),
                capture_type=SunsetCamCapture.CAPTURE_SUNSET_3,
            ).exists()
        )
