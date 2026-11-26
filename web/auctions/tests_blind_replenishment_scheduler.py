"""Blind Offer command and worker scheduling regression tests."""

import os
import subprocess
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from auctions.management.commands.replenish_founder_tienda import (
    BLIND_HANDLES,
    BLIND_RESERVE_HANDLES,
)
from auctions.models import FounderAccount, FounderListing
from auctions.utils import get_system_wallet


class BlindRecoveryCommandTests(TestCase):

    def setUp(self):
        self.platform = get_system_wallet().user
        self.curated = BLIND_HANDLES + BLIND_RESERVE_HANDLES

    def seed(self, count):
        return [
            FounderAccount.objects.create(
                handle=handle,
                owner_root=self.platform,
                status=FounderAccount.STATUS_TREASURY,
                floor_price_credits=200,
            )
            for handle in self.curated[:count]
        ]

    def active(self):
        return FounderListing.objects.filter(
            listing_source=FounderListing.SOURCE_TIENDA,
            tienda_lane=FounderListing.TIENDA_BLIND,
            status=FounderListing.STATUS_ACTIVE,
        )

    def recover(self):
        output = StringIO()

        call_command(
            "replenish_founder_blind_offers",
            stdout=output,
        )

        return output.getvalue()

    def test_command_recovers_empty_inventory(self):
        self.seed(15)

        output = self.recover()

        self.assertEqual(self.active().count(), 10)
        self.assertIn("active_before=0", output)
        self.assertIn("created=10", output)
        self.assertIn("active_after=10", output)
        self.assertIn("shortage=0", output)

    def test_command_reports_shortage_without_provisioning(self):
        self.seed(4)

        output = self.recover()

        self.assertEqual(self.active().count(), 4)
        self.assertEqual(FounderAccount.objects.count(), 4)
        self.assertIn("created=4", output)
        self.assertIn("shortage=6", output)

    def test_command_repeated_execution_is_safe(self):
        self.seed(15)
        self.recover()

        before = list(
            self.active().order_by("pk").values()
        )

        output = self.recover()

        self.assertIn("created=0", output)
        self.assertEqual(
            before,
            list(self.active().order_by("pk").values()),
        )

    def test_expiration_and_recovery_are_separate(self):
        self.seed(15)
        self.recover()

        listing = self.active().first()

        listing.ends_at = (
            timezone.now() - timedelta(seconds=1)
        )
        listing.save(update_fields=["ends_at"])

        before = FounderAccount.objects.count()

        with patch(
            "auctions.management.commands."
            "replenish_founder_tienda.Command.handle",
            side_effect=AssertionError(
                "Legacy provisioning must not run"
            ),
        ):
            call_command(
                "process_auctions",
                stdout=StringIO(),
            )

        listing.refresh_from_db()

        self.assertEqual(
            listing.status,
            FounderListing.STATUS_EXPIRED,
        )

        self.assertEqual(self.active().count(), 9)

        output = self.recover()

        self.assertIn("created=1", output)
        self.assertEqual(self.active().count(), 10)
        self.assertEqual(
            FounderAccount.objects.count(),
            before,
        )


class BlindWorkerSchedulerTests(SimpleTestCase):

    def simulate_worker(self, times, fail_recovery=False):
        worker = (
            Path(__file__).resolve().parents[1]
            / "run_auction_tasks.sh"
        )

        source = worker.read_text()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            clock = root / "uptime"
            timeline = root / "timeline"
            trace = root / "trace"
            counter = root / "counter"

            timeline.write_text(
                "\n".join(str(value) for value in times)
                + "\n"
            )

            clock.write_text(f"{times[0]}.00 0.00\n")
            counter.write_text("1\n")
            trace.touch()

            # Substitute the clock and termination boundary
            # in the temporary copy only.
            # The real scheduler remains untouched.
            anchor = "/proc/uptime"

            self.assertEqual(source.count(anchor), 1)

            script = root / "worker.sh"

            simulated = source.replace(
                anchor,
                '"$SIM_CLOCK"',
                1,
            )

            sleep_anchor = "    sleep 10\n"

            self.assertEqual(
                simulated.count(sleep_anchor),
                1,
            )

            simulated = simulated.replace(
                sleep_anchor,
                (
                    "    sleep 10\n"
                    "    SIM_STATUS=$?\n"
                    '    case "$SIM_STATUS" in\n'
                    "        0) ;;\n"
                    "        42) exit 0 ;;\n"
                    '        *) exit "$SIM_STATUS" ;;\n'
                    "    esac\n"
                ),
                1,
            )

            script.write_text(simulated)

            # Stub every management command.
            python = root / "python"

            python.write_text(
                """#!/bin/sh
printf '%s %s\\n' "$(cat "$SIM_COUNTER")" "$*" >> "$SIM_TRACE"

if [ "$2" = "replenish_founder_blind_offers" ] &&
   [ "$SIM_FAIL_RECOVERY" = "1" ] &&
   [ "$(cat "$SIM_COUNTER")" = "1" ]; then
    exit 1
fi

exit 0
"""
            )

            # Advance the synthetic clock instead of sleeping.
            # Return a sentinel status after the final iteration.
            # The temporary worker then exits normally.
            sleep = root / "sleep"

            sleep.write_text(
                """#!/bin/sh
set -eu
index="$(cat "$SIM_COUNTER")"
index=$((index + 1))

next="$(sed -n "${index}p" "$SIM_TIMELINE")"

if [ -z "$next" ]; then
    exit 42
fi

printf '%s\\n' "$index" > "$SIM_COUNTER"
printf '%s.00 0.00\\n' "$next" > "$SIM_CLOCK"
"""
            )

            python.chmod(0o700)
            sleep.chmod(0o700)

            env = os.environ.copy()

            env.update({
                "PATH": f"{root}:/usr/bin:/bin",
                "SIM_CLOCK": str(clock),
                "SIM_TIMELINE": str(timeline),
                "SIM_TRACE": str(trace),
                "SIM_COUNTER": str(counter),
                "SIM_FAIL_RECOVERY": (
                    "1" if fail_recovery else "0"
                ),
            })

            completed = subprocess.run(
                ["/bin/sh", str(script)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr,
            )

            records = trace.read_text().splitlines()

            self.assertEqual(
                [
                    int(record.split()[0])
                    for record in records
                    if record.endswith(
                        "manage.py process_auctions"
                    )
                ],
                list(range(1, len(times) + 1)),
            )

            self.assertEqual(
                int(counter.read_text().strip()),
                len(times),
            )

            return records, completed.stderr

    def recovery_iterations(self, records):
        return [
            int(record.split()[0])
            for record in records
            if record.endswith(
                "manage.py replenish_founder_blind_offers"
            )
        ]

    def test_worker_runs_recovery_at_startup(self):
        records, _ = self.simulate_worker([1000])

        self.assertEqual(
            self.recovery_iterations(records),
            [1],
        )

        self.assertEqual(
            records[:3],
            [
                "1 manage.py process_auctions",
                "1 manage.py replenish_founder_blind_offers",
                "1 manage.py process_scheduled_publications",
            ],
        )

    def test_worker_respects_five_minute_boundary(self):
        records, _ = self.simulate_worker([
            1000,
            1100,
            1299,
            1300,
            1301,
            1599,
            1600,
        ])

        self.assertEqual(
            self.recovery_iterations(records),
            [1, 4, 7],
        )

    def test_worker_retries_after_recovery_failure(self):
        records, stderr = self.simulate_worker(
            [1000, 1100, 1299, 1300],
            fail_recovery=True,
        )

        self.assertEqual(
            self.recovery_iterations(records),
            [1, 4],
        )

        self.assertIn(
            "founder_blind_replenishment_failed",
            stderr,
        )

        self.assertIn(
            "1 manage.py process_scheduled_publications",
            records,
        )

        self.assertIn(
            "4 manage.py process_scheduled_publications",
            records,
        )

    def test_worker_preserves_unrelated_periodic_tasks(self):
        records, _ = self.simulate_worker(
            [1000 + 10 * i for i in range(6)]
        )

        self.assertEqual(
            self.recovery_iterations(records),
            [1],
        )

        for command in [
            "fulfill_settled_payments",
            "process_pending_economy_deliveries",
            "process_next_founder_coin_publication",
            "process_sunsetcam_capture",
            "process_sunsetcam_promotions",
            "generate_ai_publications",
        ]:
            self.assertIn(
                f"6 manage.py {command}",
                records,
            )

        for iteration in range(1, 7):
            self.assertIn(
                f"{iteration} manage.py process_auctions",
                records,
            )

            self.assertIn(
                f"{iteration} manage.py process_scheduled_publications",
                records,
            )

        self.assertFalse(
            any(
                record.endswith(
                    "manage.py replenish_founder_tienda"
                )
                for record in records
            )
        )


    def test_worker_preserves_reminder_cycle(self):
        records, _ = self.simulate_worker(
            [1000 + 10 * i for i in range(121)]
        )

        reminders = [
            int(record.split()[0])
            for record in records
            if record.endswith(
                "manage.py send_auction_reminders"
            )
        ]

        self.assertEqual(reminders, [60, 120])

        self.assertEqual(
            self.recovery_iterations(records),
            [1, 31, 61, 91, 121],
        )

        self.assertFalse(
            any(
                "manage.py localize_feed_posts" in record
                for record in records
            )
        )

    def test_worker_preserves_localization_cycle(self):
        records, _ = self.simulate_worker(
            [1000 + 10 * i for i in range(181)]
        )

        localization = [
            int(record.split()[0])
            for record in records
            if record.endswith(
                "manage.py localize_feed_posts --limit 10"
            )
        ]

        self.assertEqual(localization, [180])

        reminders = [
            int(record.split()[0])
            for record in records
            if record.endswith(
                "manage.py send_auction_reminders"
            )
        ]

        self.assertEqual(reminders, [60, 120, 180])

        self.assertEqual(
            self.recovery_iterations(records),
            [1, 31, 61, 91, 121, 151, 181],
        )

        for command in [
            "fulfill_settled_payments",
            "process_pending_economy_deliveries",
            "process_next_founder_coin_publication",
            "process_sunsetcam_capture",
            "process_sunsetcam_promotions",
            "generate_ai_publications",
        ]:
            iterations = [
                int(record.split()[0])
                for record in records
                if record.endswith(
                    f"manage.py {command}"
                )
            ]

            self.assertEqual(
                iterations,
                list(range(6, 181, 6)),
                command,
            )

        publications = [
            int(record.split()[0])
            for record in records
            if record.endswith(
                "manage.py process_scheduled_publications"
            )
        ]

        self.assertEqual(
            publications,
            list(range(1, 182)),
        )
