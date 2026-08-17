import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    FounderLedgerHead,
    FounderOwnershipLedger,
)


def _canonical_json(payload):
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _calculate_record_hash(payload):
    canonical = _canonical_json(payload)

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


@transaction.atomic
def append_founder_ownership_ledger(
    *,
    founder_account,
    seller_root,
    buyer_root,
    transfer_type,
    sale_price_credits,
    platform_fee_credits,
    seller_proceeds_credits,
    wallet_transaction_ids,
    metadata_snapshot=None,
):
    """
    Append one authoritative Founder ownership transfer record.

    The FounderLedgerHead singleton serializes sequence allocation
    and previous-hash chaining under SELECT ... FOR UPDATE.
    """

    sale_price_credits = int(sale_price_credits)
    platform_fee_credits = int(platform_fee_credits)
    seller_proceeds_credits = int(seller_proceeds_credits)

    if sale_price_credits < 200:
        raise ValidationError(
            "Founder ledger transfers require at least 200 credits."
        )

    if (
        platform_fee_credits
        + seller_proceeds_credits
        != sale_price_credits
    ):
        raise ValidationError(
            "Founder settlement does not balance."
        )

    head, _ = FounderLedgerHead.objects.get_or_create(
        key="founder",
    )

    head = (
        FounderLedgerHead.objects
        .select_for_update()
        .get(pk=head.pk)
    )

    sequence = head.last_sequence + 1
    previous_hash = head.last_hash or ""

    metadata_snapshot = metadata_snapshot or {}

    wallet_transaction_ids = [
        int(tx_id)
        for tx_id in wallet_transaction_ids
    ]

    hash_payload = {
        "sequence": sequence,
        "founder_account_id": founder_account.pk,
        "handle": founder_account.handle,
        "seller_root_id": seller_root.pk,
        "buyer_root_id": buyer_root.pk,
        "transfer_type": transfer_type,
        "sale_price_credits": sale_price_credits,
        "platform_fee_credits": platform_fee_credits,
        "seller_proceeds_credits": seller_proceeds_credits,
        "wallet_transaction_ids": wallet_transaction_ids,
        "previous_hash": previous_hash,
        "metadata_snapshot": metadata_snapshot,
    }

    record_hash = _calculate_record_hash(
        hash_payload
    )

    ledger_record = FounderOwnershipLedger.objects.create(
        sequence=sequence,
        founder_account=founder_account,
        handle_snapshot=founder_account.handle,
        seller_root=seller_root,
        buyer_root=buyer_root,
        transfer_type=transfer_type,
        sale_price_credits=sale_price_credits,
        platform_fee_credits=platform_fee_credits,
        seller_proceeds_credits=seller_proceeds_credits,
        wallet_transaction_ids=wallet_transaction_ids,
        previous_hash=previous_hash,
        record_hash=record_hash,
        metadata_snapshot=metadata_snapshot,
    )

    head.last_sequence = sequence
    head.last_hash = record_hash

    head.save(
        update_fields=[
            "last_sequence",
            "last_hash",
            "updated_at",
        ]
    )

    return ledger_record

