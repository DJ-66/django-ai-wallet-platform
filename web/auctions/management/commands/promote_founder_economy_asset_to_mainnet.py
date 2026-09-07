from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from auctions.economy_asset_network_services import (
    EconomyAssetNetworkPromotionError,
    promote_founder_economy_asset_to_mainnet,
)
from auctions.models import EconomyAsset


class Command(BaseCommand):
    help = (
        "Promote one completed Testnet Founder economy asset "
        "into a fresh Mainnet publication lifecycle."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--asset-id",
            required=True,
            type=int,
        )

        parser.add_argument(
            "--confirm",
            required=True,
        )

    def handle(self, *args, **options):
        asset_id = options["asset_id"]

        try:
            asset = (
                EconomyAsset.objects
                .select_related("founder_account")
                .get(pk=asset_id)
            )
        except EconomyAsset.DoesNotExist as exc:
            raise CommandError(
                f"EconomyAsset {asset_id} does not exist."
            ) from exc

        expected_confirmation = (
            f"PROMOTE-"
            f"{asset.pk}-"
            f"{asset.founder_account.handle}-"
            f"TO-MAINNET"
        )

        if options["confirm"] != expected_confirmation:
            raise CommandError(
                "Confirmation mismatch. Expected: "
                + expected_confirmation
            )

        try:
            promoted = (
                promote_founder_economy_asset_to_mainnet(
                    asset.pk
                )
            )
        except EconomyAssetNetworkPromotionError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "founder_economy_asset_promoted="
                    f"{promoted.pk} "
                    f"handle=@{promoted.founder_account.handle} "
                    "network=mainnet "
                    "status=draft "
                    f"publication_key="
                    f"{promoted.metadata['publication_key']}"
                )
            )
        )
