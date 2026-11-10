"""Read-only reconciliation of account-owned platform media."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings

from auctions.models import PlatformMediaAsset


MINIMUM_RETENTION_DAYS = 7


def audit_platform_media(*, retention_days=7, now=None):
    """Report potential orphans without deleting or modifying files."""
    if (
        not isinstance(retention_days, int)
        or isinstance(retention_days, bool)
        or retention_days < MINIMUM_RETENTION_DAYS
    ):
        raise ValueError("Retention must be at least seven days.")

    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(days=retention_days)

    media_root = Path(settings.MEDIA_ROOT).resolve(strict=True)
    storage_root = media_root / "platform_media"

    referenced = set(
        PlatformMediaAsset.objects
        .exclude(image="")
        .values_list("image", flat=True)
    )

    stored = set()
    candidates = []
    symlinks = []

    if storage_root.exists():
        if storage_root.is_symlink():
            raise ValueError("Symlinked platform media root.")

        for path in storage_root.rglob("*"):
            relative = path.relative_to(media_root).as_posix()

            if path.is_symlink():
                symlinks.append(relative)
                continue

            if not path.is_file():
                continue

            stored.add(relative)

            if relative in referenced:
                continue

            modified = datetime.fromtimestamp(
                path.stat().st_mtime,
                timezone.utc,
            )

            if modified <= cutoff:
                candidates.append(relative)

    return {
        "stored_count": len(stored),
        "referenced_count": len(referenced),
        "unreferenced_count": len(stored - referenced),
        "missing_count": len(referenced - stored),
        "retention_eligible_count": len(candidates),
        "symlink_count": len(symlinks),
        "candidates": sorted(candidates),
        "missing": sorted(referenced - stored),
        "symlinks": sorted(symlinks),
    }
