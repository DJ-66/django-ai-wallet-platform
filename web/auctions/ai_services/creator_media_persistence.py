"""Bounded, non-destructive creator media registration."""

import json
from hashlib import sha256
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from auctions.models import (
    PlatformMediaAsset,
    ScheduledPublication,
)
from auctions.platform_media_services import save_platform_media
from auctions.management.commands.generate_ai_publications import (
    IMAGE_EXTENSIONS,
    EXCLUDED_DIRECTORY_NAMES,
)
from core.image_utils import process_fanz_image_upload
from auctions.ai_services.secure_creator_media import (
    read_creator_media,
)


MAX_SOURCE_BYTES = 40 * 1024 * 1024
MAX_WEBP_BYTES = 1024 * 1024
MAX_BATCH_SIZE = 30

MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "ai_creator_media_manifest.json"
)


def _trusted_creator_for_account(account):
    """Resolve an existing account against the server-side manifest."""
    manifest = json.loads(MANIFEST_PATH.read_text())

    matches = [
        creator
        for creator in manifest["creators"]
        if creator["account"].casefold()
        == account.username.casefold()
    ]

    if len(matches) != 1:
        raise ValidationError(
            "Account is not uniquely authorized by creator manifest."
        )

    return matches[0]


def import_creator_media(
    *,
    account,
    source_root,
    relative_paths,
):
    """Register approved creator images without deleting originals."""
    connection = transaction.get_connection()

    if connection.in_atomic_block or not connection.get_autocommit():
        raise RuntimeError(
            "Creator media import requires an autocommit context."
        )

    if not isinstance(relative_paths, (list, tuple)):
        raise ValueError("Relative paths must be a list or tuple.")

    if not 1 <= len(relative_paths) <= MAX_BATCH_SIZE:
        raise ValueError("Import batch must contain 1-30 images.")

    creator = _trusted_creator_for_account(account)

    packs = creator.get("packs")

    if not isinstance(packs, list) or not packs:
        raise ValidationError("Invalid creator pack assignment.")

    root_path = Path(source_root)

    if root_path.is_symlink():
        raise ValidationError("Symlinked media root rejected.")

    root = root_path.resolve(strict=True)

    if not root.is_dir():
        raise ValidationError("Invalid creator media root.")

    approved = set()
    approved_relative = set()

    for pack_name in packs:
        if not isinstance(pack_name, str) or not pack_name:
            raise ValidationError("Invalid creator pack name.")

        pack_relative = Path(pack_name)

        if (
            pack_relative.is_absolute()
            or ".." in pack_relative.parts
            or "." in pack_relative.parts
        ):
            raise ValidationError("Unsafe creator pack path.")

        pack = root / pack_relative

        if pack.is_symlink():
            raise ValidationError("Symlinked creator pack rejected.")

        resolved_pack = pack.resolve(strict=True)

        if not resolved_pack.is_relative_to(root):
            raise ValidationError("Creator pack escapes media root.")

        if not resolved_pack.is_dir():
            raise ValidationError("Creator pack is not a directory.")

        approved.add(resolved_pack)
        approved_relative.add(pack_relative)

    # Match the legacy generator's non-failed publication history.
    already_scheduled = set(
        ScheduledPublication.objects.filter(
            creator=account,
        )
        .exclude(
            status=ScheduledPublication.STATUS_FAILED,
        )
        .values_list("source_path", flat=True)
    )

    created = 0
    duplicates = 0
    rejected = 0

    for relative in relative_paths:
        if not isinstance(relative, str) or not relative:
            rejected += 1
            continue

        relative_path = Path(relative)

        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or "." in relative_path.parts
            or relative_path.suffix.lower() not in IMAGE_EXTENSIONS
        ):
            rejected += 1
            continue

        if any(
            part.lower() in EXCLUDED_DIRECTORY_NAMES
            for part in relative_path.parts[:-1]
        ):
            rejected += 1
            continue

        if (
            relative == creator.get("avatar_source")
            or relative in already_scheduled
        ):
            rejected += 1
            continue

        # Authorize by manifest-owned relative pack identity.
        # The secure reader opens each component without symlinks.
        authorized = any(
            relative_path.is_relative_to(pack_relative)
            and relative_path != pack_relative
            for pack_relative in approved_relative
        )

        if not authorized:
            rejected += 1
            continue

        try:
            data = read_creator_media(
                source_root=root,
                relative_path=relative,
            )
        except ValidationError:
            rejected += 1
            continue

        digest = sha256(data).hexdigest()

        if PlatformMediaAsset.objects.filter(
            account=account,
            sha256=digest,
        ).exists():
            duplicates += 1
            continue

        upload = SimpleUploadedFile(relative_path.name, data)

        try:
            processed = process_fanz_image_upload(
                upload,
                watermark=False,
                platform_footer=False,
                max_width=1600,
                max_height=1600,
                quality=90,
                max_output_bytes=MAX_WEBP_BYTES,
            )

            processed.seek(0)

            with Image.open(processed) as image:
                if image.format != "WEBP":
                    raise ValidationError("Invalid WebP output.")

                image.verify()

            if processed.size > MAX_WEBP_BYTES:
                raise ValidationError("WebP output exceeds limit.")

            processed.seek(0)

        except (
            ValidationError,
            UnidentifiedImageError,
            OSError,
            ValueError,
        ):
            rejected += 1
            continue

        new_count, duplicate_count = save_platform_media(
            account,
            [{
                "file": processed,
                "sha256": digest,
            }],
        )

        created += new_count
        duplicates += duplicate_count

    return {
        "created": created,
        "duplicates": duplicates,
        "rejected": rejected,
    }
