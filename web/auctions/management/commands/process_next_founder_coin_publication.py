from django.core.management import call_command
from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from auctions.models import EconomyAsset

from .process_founder_coin_publication import (
    prepared_payload_path,
)


class Command(BaseCommand):
    help = (
        "Process at most one pending Founder vending "
        "creator-coin publication. Missing prepared "
        "artifacts are skipped safely."
    )

    def handle(self, *args, **options):
        assets = (
            EconomyAsset.objects
            .select_related("founder_account")
            .filter(
                status=EconomyAsset.STATUS_DRAFT,
                coin_type__isnull=True,
                genesis_tx_digest__isnull=True,
                metadata__issuance_source="founder_vending",
            )
            .order_by("pk")
        )

        found_candidate = False

        for asset in assets:
            metadata = dict(asset.metadata or {})

            recipient = (
                metadata.get(
                    "intended_recipient_address"
                )
                or ""
            ).strip()

            if not recipient:
                continue

            found_candidate = True

            payload_path = prepared_payload_path(
                asset
            )

            if not payload_path.is_file():
                self.stdout.write(
                    (
                        "founder_coin_worker="
                        "WAITING_FOR_PREPARED_PAYLOAD "
                        f"asset_id={asset.pk} "
                        f"handle=@{asset.founder_account.handle}"
                    )
                )
                return

            self.stdout.write(
                (
                    "founder_coin_worker=PROCESSING "
                    f"asset_id={asset.pk} "
                    f"handle=@{asset.founder_account.handle}"
                )
            )

            try:
                call_command(
                    "process_founder_coin_publication",
                    asset_id=asset.pk,
                    stdout=self.stdout,
                    stderr=self.stderr,
                )
            except CommandError:
                raise

            return

        if not found_candidate:
            self.stdout.write(
                "founder_coin_worker=EMPTY"
            )
