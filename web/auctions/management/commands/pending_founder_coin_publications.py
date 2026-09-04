import json

from django.core.management.base import BaseCommand

from auctions.models import EconomyAsset


class Command(BaseCommand):
    help = (
        "List pending Founder vending creator-coin "
        "publication preparation jobs."
    )

    def handle(self, *args, **options):
        assets = (
            EconomyAsset.objects
            .select_related("founder_account")
            .filter(
                status=EconomyAsset.STATUS_DRAFT,
                coin_type__isnull=True,
                genesis_tx_digest__isnull=True,
                metadata__issuance_source__in=[
                    "founder_vending",
                    "founder_ownership",
                ],
            )
            .order_by("pk")
        )

        count = 0

        for asset in assets:
            metadata = dict(
                asset.metadata or {}
            )

            recipient = (
                metadata.get(
                    "intended_recipient_address"
                )
                or ""
            ).strip()

            if not recipient:
                continue

            handle = asset.founder_account.handle

            package_name = (
                metadata.get("generated_package")
                or f"fanz_creator_{handle}"
            )

            publication_key = (
                metadata.get("publication_key")
                or (
                    f"founder-{asset.pk}-"
                    f"{handle}-v1"
                )
            )

            publication_network = str(
                metadata.get(
                    "publication_network",
                    "",
                )
            ).strip().lower()

            if publication_network not in {
                "testnet",
                "mainnet",
            }:
                continue

            record = {
                "economy_asset_id": asset.pk,
                "founder_account_id": (
                    asset.founder_account_id
                ),
                "handle": handle,
                "name": asset.name,
                "symbol": asset.symbol,
                "chain": asset.chain,
                "network": publication_network,
                "decimals": asset.decimals,
                "genesis_supply_base_units": (
                    asset.genesis_supply_base_units
                ),
                "generated_package": package_name,
                "publication_key": publication_key,
                "recipient_address": recipient,
            }

            self.stdout.write(
                json.dumps(
                    record,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )

            count += 1

        self.stderr.write(
            f"pending_founder_coin_publications={count}"
        )
