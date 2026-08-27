from django.core.management.base import BaseCommand

from auctions.economy_delivery_services import (
    EconomyDeliveryError,
    process_pending_economy_delivery,
    record_economy_delivery_error,
)
from auctions.models import EconomyAssetDelivery


class Command(BaseCommand):
    help = "Prepare pending FANZ economy-asset deliveries."

    def handle(self, *args, **options):
        delivery_ids = list(
            EconomyAssetDelivery.objects.filter(
                status=EconomyAssetDelivery.STATUS_PENDING,
            )
            .order_by("id")
            .values_list("id", flat=True)[:100]
        )

        prepared = 0
        failed = 0

        for delivery_id in delivery_ids:
            try:
                _, changed = process_pending_economy_delivery(
                    delivery_id
                )

                if changed:
                    prepared += 1

            except EconomyDeliveryError as exc:
                failed += 1

                record_economy_delivery_error(
                    delivery_id,
                    str(exc),
                )

                self.stderr.write(
                    self.style.WARNING(
                        f"Economy delivery {delivery_id} "
                        f"not prepared: {exc}"
                    )
                )

        self.stdout.write(
            f"Prepared {prepared} economy deliveries. "
            f"Failed {failed}."
        )
