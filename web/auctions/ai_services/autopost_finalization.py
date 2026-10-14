"""Safe finalization of ready AutoPost publications."""

from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.utils import timezone

from auctions.ai_services.autopost_entitlements import (
    has_active_autopost_entitlement,
)
from auctions.management.commands.repair_creator_captions import (
    validate_recovery_translations,
)
from auctions.models import AutoPostPublication


def validate_autopost_ready(publication, *, at=None):
    """Validate a due, entitled AutoPost publication; write nothing."""
    now = at if at is not None else timezone.now()

    if publication.status != AutoPostPublication.STATUS_READY:
        raise ValidationError("AutoPost publication is not ready.")

    if publication.scheduled_for > now:
        raise ValidationError("AutoPost publication is not due yet.")

    config = publication.configuration

    if not config.enabled or not config.account.is_active:
        raise ValidationError("AutoPost account is disabled.")

    if not has_active_autopost_entitlement(
        account_id=config.account_id,
        at=now,
    ):
        raise ValidationError("Active AutoPost entitlement required.")

    if publication.media_asset.account_id != config.account_id:
        raise ValidationError("Reserved media belongs to another account.")

    tags = publication.reserved_hashtags
    translations = publication.translations

    try:
        validate_recovery_translations(translations, tags)
    except (CommandError, AttributeError, TypeError) as exc:
        raise ValidationError(
            "AutoPost translations are incomplete or invalid."
        ) from exc

    # Verify the exact promotional snapshot before publication.
    snapshot = publication.suffix_translations
    campaign = publication.campaign
    destination = publication.destination_url

    if not isinstance(snapshot, dict) or set(snapshot) != {
        "en", "es", "pt"
    }:
        raise ValidationError("Missing frozen promotional copy.")

    if bool(campaign) != bool(destination):
        raise ValidationError("CTA destination mismatch.")

    for language in ("en", "es", "pt"):
        closer = snapshot[language]
        if (
            not isinstance(closer, str)
            or not closer.strip()
            or "\n" in closer
        ):
            raise ValidationError("Invalid frozen promotional wording.")

        caption, _ = translations[language]["content"].split("\n\n")
        lines = caption.splitlines()

        if campaign:
            if len(lines) < 2 or lines[-2:] != [
                closer.strip(), destination
            ]:
                raise ValidationError(
                    f"{language} frozen CTA mismatch."
                )
        elif not lines or lines[-1] != closer.strip():
            raise ValidationError(
                f"{language} frozen personality mismatch."
            )

    if publication.feed_post_id is not None:
        raise ValidationError("AutoPost already has a feed post.")

    return True


def publish_ready_autopost(publication_id):
    """Publish one due, validated AutoPost exactly once."""
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError

    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import transaction

    from auctions.feed_publishing import publish_feed_post
    from auctions.models import FeedPostTranslation

    saved_files = []

    def track_file(storage, name):
        saved_files.append((storage, name))

    try:
        with transaction.atomic():
            publication = (
                AutoPostPublication.objects
                .select_for_update()
                .select_related(
                    "configuration__account",
                    "media_asset",
                )
                .get(pk=publication_id)
            )

            if publication.status == AutoPostPublication.STATUS_PUBLISHED:
                if publication.feed_post_id:
                    return publication.feed_post
                raise ValidationError("Published AutoPost has no feed post.")

            validate_autopost_ready(publication)

            asset = publication.media_asset
            with asset.image.open("rb") as source:
                image_bytes = source.read()

            # Determine the real format, not the storage filename.
            try:
                with Image.open(BytesIO(image_bytes)) as image:
                    image.verify()
                    image_format = image.format
            except (UnidentifiedImageError, OSError) as exc:
                raise ValidationError(
                    "Reserved AutoPost media is not a valid image."
                ) from exc

            formats = {
                "JPEG": ("jpg", "image/jpeg"),
                "PNG": ("png", "image/png"),
                "WEBP": ("webp", "image/webp"),
                "AVIF": ("avif", "image/avif"),
            }

            if image_format not in formats:
                raise ValidationError(
                    "Unsupported AutoPost image format."
                )

            extension, content_type = formats[image_format]

            upload = SimpleUploadedFile(
                f"autopost-{publication.pk}.{extension}",
                image_bytes,
                content_type=content_type,
            )

            english = publication.translations["en"]

            post = publish_feed_post(
                user=publication.configuration.account,
                title=english["title"],
                content=english["content"],
                uploads=[upload],
                is_public=True,
                is_paid=False,
                on_media_saved=track_file,
            )

            for language in ("en", "es", "pt"):
                copy = publication.translations[language]

                FeedPostTranslation.objects.create(
                    post=post,
                    language=language,
                    title=copy["title"],
                    content=copy["content"],
                )

            publication.feed_post = post
            publication.status = AutoPostPublication.STATUS_PUBLISHED
            publication.save(update_fields=[
                "feed_post", "status", "updated_at",
            ])

            return post

    except Exception:
        for storage, name in reversed(saved_files):
            try:
                storage.delete(name)
            except Exception:
                pass
        raise
