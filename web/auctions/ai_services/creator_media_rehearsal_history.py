"""Minimal legacy source exclusions for isolated rehearsal only."""

from hashlib import sha256

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from auctions.models import ScheduledPublication


REHEARSAL_DATABASE = "fanz_media_rehearsal"


def seed_rehearsal_history(rows):
    """Create synthetic draft records representing excluded source paths."""
    if connection.settings_dict["NAME"] != REHEARSAL_DATABASE:
        raise RuntimeError("Rehearsal database required.")

    if not isinstance(rows, list):
        raise ValidationError("History fixture must be a list.")

    if not rows:
        raise ValidationError("History fixture cannot be empty.")

    if ScheduledPublication.objects.exists():
        raise RuntimeError("Rehearsal history already populated.")

    User = get_user_model()

    users = {
        user.username.casefold(): user
        for user in User.objects.all()
    }

    if len(users) != 46:
        raise RuntimeError("Expected 46 rehearsal identities.")

    prepared = []
    seen = set()
    covered = set()

    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError("Invalid history row.")

        account = row.get("account")
        source_path = row.get("source_path")

        if not isinstance(account, str):
            raise ValidationError("Invalid creator account.")

        if not isinstance(source_path, str) or not source_path:
            raise ValidationError("Invalid source path.")

        key = account.casefold()

        if key not in users:
            raise ValidationError("Unknown rehearsal creator.")

        identity = (key, source_path)

        if identity in seen:
            continue

        seen.add(identity)
        covered.add(key)

        digest = sha256(
            (key + ":" + source_path).encode()
        ).hexdigest()

        prepared.append(
            ScheduledPublication(
                creator=users[key],
                publication_key="rehearsal:" + digest,
                source_path=source_path,
                title="Rehearsal exclusion",
                content="Synthetic history fixture.",
                scheduled_for=timezone.now(),
                status=ScheduledPublication.STATUS_DRAFT,
            )
        )

    if len(covered) != 46:
        raise ValidationError(
            "History fixture does not cover all 46 creators."
        )

    with transaction.atomic():
        ScheduledPublication.objects.bulk_create(
            prepared,
            batch_size=250,
        )

    return {
        "creators": len(covered),
        "exclusions": len(prepared),
    }
