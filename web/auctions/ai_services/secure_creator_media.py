"""Descriptor-based, bounded creator media reads."""

import os
import stat
from pathlib import Path

from django.core.exceptions import ValidationError


MAX_SOURCE_BYTES = 40 * 1024 * 1024


def read_creator_media(*, source_root, relative_path):
    """Read one regular file without following directory symlinks."""
    if not isinstance(relative_path, str) or not relative_path:
        raise ValidationError("Invalid media path.")

    relative = Path(relative_path)

    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
        or not relative.parts
    ):
        raise ValidationError("Unsafe media path.")

    root_path = Path(source_root)

    if root_path.is_symlink():
        raise ValidationError("Symlinked media root rejected.")

    root_fd = None
    opened = []

    flags = (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | os.O_CLOEXEC
        | os.O_NONBLOCK
    )

    try:
        root_fd = os.open(
            root_path,
            flags | os.O_DIRECTORY,
        )

        current_fd = root_fd

        for component in relative.parts[:-1]:
            directory_fd = os.open(
                component,
                flags | os.O_DIRECTORY,
                dir_fd=current_fd,
            )

            opened.append(directory_fd)
            current_fd = directory_fd

        file_fd = os.open(
            relative.parts[-1],
            flags,
            dir_fd=current_fd,
        )

        opened.append(file_fd)

        before = os.fstat(file_fd)

        if not stat.S_ISREG(before.st_mode):
            raise ValidationError("Media source is not a regular file.")

        if before.st_size > MAX_SOURCE_BYTES:
            raise ValidationError("Media source exceeds 40 MiB.")

        chunks = []
        total = 0

        while True:
            chunk = os.read(file_fd, 1024 * 1024)

            if not chunk:
                break

            total += len(chunk)

            if total > MAX_SOURCE_BYTES:
                raise ValidationError("Media source exceeds 40 MiB.")

            chunks.append(chunk)

        after = os.fstat(file_fd)

        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
            or total != after.st_size
        ):
            raise ValidationError("Media source changed during read.")

        return b"".join(chunks)

    except (OSError, ValueError) as exc:
        raise ValidationError(
            "Unable to read approved creator media."
        ) from exc

    finally:
        for fd in reversed(opened):
            os.close(fd)

        if root_fd is not None:
            os.close(root_fd)
