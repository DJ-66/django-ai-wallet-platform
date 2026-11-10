from unittest.mock import patch

from django.test import SimpleTestCase

from auctions.management.commands.process_scheduled_publications import Command
from auctions.models import ScheduledPublication


class ScheduledPublicationStateGuardTests(SimpleTestCase):
    def test_stale_failure_requires_publishing_state(self):
        with patch(
            "auctions.management.commands."
            "process_scheduled_publications."
            "ScheduledPublication.objects.filter"
        ) as mocked_filter:
            mocked_filter.return_value.update.return_value = 0

            Command()._mark_failed(
                12345,
                "stale worker failure",
            )

            mocked_filter.assert_called_once_with(
                pk=12345,
                status=ScheduledPublication.STATUS_PUBLISHING,
            )

            mocked_filter.return_value.update.assert_called_once_with(
                status=ScheduledPublication.STATUS_FAILED,
                last_error="stale worker failure",
                updated_at=mocked_filter.return_value.update.call_args.kwargs[
                    "updated_at"
                ],
            )
