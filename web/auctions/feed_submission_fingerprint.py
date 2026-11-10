"""Deterministic fingerprints for interactive feed submissions."""

import hashlib
import json


FIELDS = (
    "title",
    "content",
    "media_type",
    "is_public",
    "is_paid",
    "unlock_price",
    "alltags_requested",
    "alltags_confirmed",
)


def fingerprint_feed_submission(post_data, files):
    digest = hashlib.sha256()

    fields = {
        name: post_data.getlist(name)
        for name in FIELDS
    }

    encoded = json.dumps(
        fields,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)

    uploads = files.getlist("images")

    digest.update(len(uploads).to_bytes(8, "big"))

    for upload in uploads:
        metadata = json.dumps(
            {
                "name": upload.name,
                "size": upload.size,
                "content_type": getattr(
                    upload,
                    "content_type",
                    "",
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        digest.update(len(metadata).to_bytes(8, "big"))
        digest.update(metadata)

        position = upload.tell()

        try:
            upload.seek(0)

            file_digest = hashlib.sha256()

            for chunk in upload.chunks():
                file_digest.update(chunk)

            digest.update(file_digest.digest())
        finally:
            upload.seek(position)

    return digest.hexdigest()
