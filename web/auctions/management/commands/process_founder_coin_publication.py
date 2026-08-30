import json
from pathlib import Path

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from auctions.economy_asset_publication_services import (
    EconomyAssetPublicationError,
    reconcile_confirmed_creator_publication,
)
from auctions.economy_asset_supply_services import (
    EconomyAssetSupplyError,
    verify_economy_asset_fixed_supply,
)
from auctions.models import EconomyAsset
from auctions.sui_adapter import (
    SuiAdapterConflict,
    SuiAdapterError,
    accept_creator_publication,
    get_creator_publication,
    prepare_creator_publication,
    reconcile_creator_publication,
    submit_creator_publication,
)


REPO_ROOT = Path(__file__).resolve().parents[3]

PREPARED_ROOT = (
    REPO_ROOT
    / "sui"
    / "prepared-publications"
)


class FounderCoinPublicationProcessError(
    RuntimeError
):
    pass


def publication_key_for_asset(asset):
    metadata = dict(asset.metadata or {})

    return (
        metadata.get("publication_key")
        or (
            f"founder-{asset.pk}-"
            f"{asset.founder_account.handle}-v1"
        )
    )


def prepared_payload_path(asset):
    publication_key = publication_key_for_asset(
        asset
    )

    return (
        PREPARED_ROOT
        / f"{publication_key}.json"
    )


def load_prepared_payload(asset):
    path = prepared_payload_path(asset)

    try:
        payload = json.loads(
            path.read_text()
        )
    except FileNotFoundError as exc:
        raise FounderCoinPublicationProcessError(
            f"Prepared publication not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise FounderCoinPublicationProcessError(
            f"Prepared publication is invalid JSON: {path}"
        ) from exc

    required = {
        "publication_key",
        "chain",
        "module_name",
        "coin_struct_name",
        "source_sha256",
        "artifact_sha256",
        "modules",
        "dependency_ids",
        "recipient_address",
    }

    missing = sorted(
        required - set(payload)
    )

    if missing:
        raise FounderCoinPublicationProcessError(
            "Prepared publication missing fields: "
            + ", ".join(missing)
        )

    expected_key = publication_key_for_asset(
        asset
    )

    expected_module = (
        f"{asset.founder_account.handle}_fanz"
    )

    expected_struct = (
        f"{asset.founder_account.handle.upper()}"
        "_FANZ"
    )

    if payload["publication_key"] != expected_key:
        raise FounderCoinPublicationProcessError(
            "Prepared publication_key does not match EconomyAsset."
        )

    if payload["chain"] != asset.chain:
        raise FounderCoinPublicationProcessError(
            "Prepared publication chain does not match EconomyAsset."
        )

    if payload["module_name"] != expected_module:
        raise FounderCoinPublicationProcessError(
            "Prepared publication module does not match EconomyAsset."
        )

    if payload["coin_struct_name"] != expected_struct:
        raise FounderCoinPublicationProcessError(
            "Prepared publication coin struct does not match EconomyAsset."
        )

    expected_recipient = str(
        (asset.metadata or {}).get(
            "intended_recipient_address",
            "",
        )
    ).strip().lower()

    if (
        str(payload["recipient_address"]).strip().lower()
        != expected_recipient
    ):
        raise FounderCoinPublicationProcessError(
            "Prepared publication recipient does not match EconomyAsset."
        )

    return payload, path


def publication_from_response(response):
    publication = response.get(
        "publication"
    )

    if not isinstance(publication, dict):
        raise FounderCoinPublicationProcessError(
            "FANZ Sui response contained no publication object."
        )

    return publication


def get_remote_publication(publication_key):
    try:
        response = get_creator_publication(
            publication_key
        )
    except SuiAdapterError as exc:
        message = str(exc)

        if "HTTP 404" in message:
            return None

        raise

    return publication_from_response(
        response
    )


def is_prepare_gate_closed(exc):
    return (
        "HTTP 400" in str(exc)
        and (
            "preparation is disabled"
            in str(exc).lower()
        )
    )


def is_submit_gate_closed(exc):
    message = str(exc).lower()

    return (
        "http 400" in message
        and (
            "submission is disabled"
            in message
            or "publication submission"
            in message
        )
    )


class Command(BaseCommand):
    help = (
        "Advance one prepared Founder vending "
        "creator-coin publication through the "
        "FANZ Sui journal without changing gates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--asset-id",
            required=True,
            type=int,
        )

    def handle(self, *args, **options):
        asset = (
            EconomyAsset.objects
            .select_related("founder_account")
            .get(pk=options["asset_id"])
        )

        metadata = dict(asset.metadata or {})

        if (
            metadata.get("issuance_source")
            != "founder_vending"
        ):
            raise CommandError(
                "EconomyAsset is not a Founder vending asset."
            )

        if (
            asset.coin_type
            and asset.genesis_tx_digest
            and asset.supply_fixed_at
        ):
            self.stdout.write(
                "founder_coin_publication=ALREADY_COMPLETE"
            )
            return

        publication_key = (
            publication_key_for_asset(asset)
        )

        payload, payload_path = (
            load_prepared_payload(asset)
        )

        self.stdout.write(
            json.dumps(
                {
                    "economy_asset_id": asset.pk,
                    "handle":
                        asset.founder_account.handle,
                    "publication_key":
                        publication_key,
                    "payload":
                        str(payload_path),
                },
                sort_keys=True,
            )
        )

        remote = get_remote_publication(
            publication_key
        )

        if remote is None:
            try:
                response = (
                    accept_creator_publication(
                        payload
                    )
                )
            except SuiAdapterConflict as exc:
                raise CommandError(
                    "Creator publication acceptance conflict."
                ) from exc
            except SuiAdapterError as exc:
                raise CommandError(
                    str(exc)
                ) from exc

            remote = publication_from_response(
                response
            )

            self.stdout.write(
                "founder_coin_publication=ACCEPTED"
            )

        state = remote.get("state")

        self.stdout.write(
            f"journal_state={state}"
        )

        if state == "accepted":
            try:
                response = (
                    prepare_creator_publication(
                        publication_key
                    )
                )
            except SuiAdapterError as exc:
                if is_prepare_gate_closed(exc):
                    self.stdout.write(
                        "founder_coin_publication=STOP_PREPARE_GATE_CLOSED"
                    )
                    return

                raise CommandError(
                    str(exc)
                ) from exc

            remote = publication_from_response(
                response
            )

            state = remote.get("state")

            self.stdout.write(
                f"journal_state={state}"
            )

        if state == "prepared":
            try:
                response = (
                    submit_creator_publication(
                        publication_key
                    )
                )
            except SuiAdapterError as exc:
                if is_submit_gate_closed(exc):
                    self.stdout.write(
                        "founder_coin_publication=STOP_SUBMIT_GATE_CLOSED"
                    )
                    return

                raise CommandError(
                    str(exc)
                ) from exc

            remote = publication_from_response(
                response
            )

            state = remote.get("state")

            self.stdout.write(
                f"journal_state={state}"
            )

        if state == "submitted":
            try:
                response = (
                    reconcile_creator_publication(
                        publication_key
                    )
                )
            except SuiAdapterError as exc:
                raise CommandError(
                    str(exc)
                ) from exc

            remote = publication_from_response(
                response
            )

            state = remote.get("state")

            self.stdout.write(
                f"journal_state={state}"
            )

        if state != "confirmed":
            self.stdout.write(
                "founder_coin_publication=STOP_NOT_CONFIRMED"
            )
            return

        try:
            asset, publication_changed = (
                reconcile_confirmed_creator_publication(
                    asset.pk,
                    publication_key,
                )
            )
        except EconomyAssetPublicationError as exc:
            raise CommandError(
                str(exc)
            ) from exc

        try:
            asset, supply_changed = (
                verify_economy_asset_fixed_supply(
                    asset.pk,
                    publication_key,
                )
            )
        except EconomyAssetSupplyError as exc:
            raise CommandError(
                str(exc)
            ) from exc

        self.stdout.write(
            json.dumps(
                {
                    "economy_asset_id":
                        asset.pk,
                    "status":
                        asset.status,
                    "coin_type":
                        asset.coin_type,
                    "genesis_tx_digest":
                        asset.genesis_tx_digest,
                    "supply_fixed_at":
                        (
                            asset.supply_fixed_at
                            .isoformat()
                            if asset.supply_fixed_at
                            else None
                        ),
                    "publication_changed":
                        publication_changed,
                    "supply_changed":
                        supply_changed,
                },
                sort_keys=True,
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "founder_coin_publication=COMPLETE"
            )
        )
