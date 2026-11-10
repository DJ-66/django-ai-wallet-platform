"""Bounded creator-pack media selection for unified AutoPost."""

from pathlib import Path

from django.core.exceptions import ValidationError

from auctions.management.commands.generate_ai_publications import (
    IMAGE_EXTENSIONS,
    EXCLUDED_DIRECTORY_NAMES,
)


def select_creator_media(
    *,
    source_root,
    creator,
    already_scheduled,
    already_imported=(),
    limit=2,
):
    """Select eligible files without modifying media or database state."""
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("Import limit must be an integer.")

    if not 1 <= limit <= 30:
        raise ValueError("Import limit must be between 1 and 30.")

    root = Path(source_root).resolve(strict=True)

    if not root.is_dir():
        raise ValidationError("Creator media root is not a directory.")

    reserved_avatar = creator.get("avatar_source")
    excluded = set(already_scheduled) | set(already_imported)
    eligible = set()

    for pack_name in creator["packs"]:
        pack = root / pack_name

        if pack.is_symlink():
            raise ValidationError("Symlinked creator pack rejected.")

        resolved_pack = pack.resolve(strict=True)

        if not resolved_pack.is_relative_to(root):
            raise ValidationError("Creator pack escapes source root.")

        if not resolved_pack.is_dir():
            raise ValidationError("Creator pack is not a directory.")

        for path in resolved_pack.rglob("*"):
            if path.is_symlink():
                continue

            if not path.is_file():
                continue

            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            relative = path.relative_to(root)

            if any(
                part.lower() in EXCLUDED_DIRECTORY_NAMES
                for part in relative.parts[:-1]
            ):
                continue

            relative_name = str(relative)

            if relative_name == reserved_avatar:
                continue

            if relative_name in excluded:
                continue

            eligible.add(relative_name)

    return sorted(eligible)[:limit]
