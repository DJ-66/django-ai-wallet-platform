from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone

from auctions.feed_publishing import publish_feed_post
from auctions.models import (
    FeedPostTranslation,
    PlatformMediaAsset,
    ScheduledPublication,
    UserProfile,
)
from auctions.promotional_campaign_publishing import (
    prepare_branded_translation,
    prepare_promotional_campaign,
)


def publish_promotional_publication(publication_id):
    """
    Publish one already-claimed promotional publication.

    The caller must claim the queued publication first.
    Reusable media is never consumed or deleted.
    """

    saved_files = []

    try:
        return _publish_promotional_atomic(
            publication_id,
            saved_files,
        )
    except Exception:
        for storage, name in reversed(saved_files):
            try:
                storage.delete(name)
            except Exception:
                # Cleanup failure must not hide the original
                # publication error.
                pass
        raise


def _publish_promotional_atomic(publication_id, saved_files):
    with transaction.atomic():
        publication = (
            ScheduledPublication.objects
            .select_related("creator", "media_asset")
            .select_for_update(of=("self",))
            .get(pk=publication_id)
        )

        if publication.status != ScheduledPublication.STATUS_PUBLISHING:
            raise ValidationError(
                "Promotional publication is not claimed."
            )

        if publication.feed_post_id:
            raise ValidationError(
                "Promotional publication already has a feed post."
            )

        if publication.media_asset_id is None:
            raise ValidationError(
                "Promotional publication has no media asset."
            )

        # Recheck platform authorization at publication time.
        # Lock the profile row for the duration of publishing.
        profile = (
            UserProfile.objects
            .select_for_update()
            .filter(user_id=publication.creator_id)
            .first()
        )

        if (
            profile is None
            or not profile.is_platform_account
        ):
            raise ValidationError(
                "Promotional publishing requires "
                "an authorized platform account."
            )

        # Lock the reusable image while validating and
        # publishing. The Media Manager toggle acquires
        # this same row lock.
        asset = (
            PlatformMediaAsset.objects
            .select_for_update()
            .get(pk=publication.media_asset_id)
        )

        if publication.source_path:
            raise ValidationError(
                "Promotional publication has conflicting sources."
            )

        if asset.account_id != publication.creator_id:
            raise ValidationError(
                "Promotional media belongs to another account."
            )

        if not asset.is_active:
            raise ValidationError(
                "Promotional media is inactive."
            )

        if not asset.image.storage.exists(asset.image.name):
            raise ValidationError(
                "Promotional source image is missing."
            )

        if publication.campaign_key:
            prepared = prepare_promotional_campaign(
                publication,
                asset,
            )

            by_language = {
                item.language: item
                for item in prepared
            }

            if set(by_language) != {"en", "es", "pt"}:
                raise RuntimeError(
                    "Incomplete promotional translations."
                )

            english = by_language["en"]

            upload = SimpleUploadedFile(
                "campaign-en.webp",
                english.image_bytes,
                content_type="image/webp",
            )

            post = publish_feed_post(
                user=publication.creator,
                title=english.headline,
                content=english.content,
                uploads=[upload],
                is_public=True,
                is_paid=False,
                unlock_price=0,
                on_media_saved=lambda storage, name: (
                    saved_files.append((storage, name))
                ),
            )

            media = post.media.filter(
                is_active=True,
            ).first()

            if (
                media is None
                or not media.file.storage.exists(media.file.name)
            ):
                raise RuntimeError(
                    "Published campaign media is missing."
                )

            for language in ("en", "es", "pt"):
                item = by_language[language]

                translation = FeedPostTranslation(
                    post=post,
                    language=language,
                    title=item.headline,
                    content=item.content,
                )

                if language == "en":
                    # English uses the base feed image.
                    # No duplicate file is needed.
                    translation.save()
                    continue

                branded = prepare_branded_translation(
                    item,
                    username=publication.creator.username,
                )

                translation.image.save(
                    f"campaign-{post.pk}-{language}.webp",
                    ContentFile(branded.read()),
                    save=False,
                )

                saved_files.append((
                    translation.image.storage,
                    translation.image.name,
                ))

                translation.save()

            publication.feed_post = post
            publication.status = (
                ScheduledPublication.STATUS_PUBLISHED
            )
            publication.published_at = timezone.now()
            publication.last_error = ""

            publication.save(
                update_fields=[
                    "feed_post",
                    "status",
                    "published_at",
                    "last_error",
                    "updated_at",
                ]
            )

            return post

        with asset.image.open("rb") as source:
            upload = SimpleUploadedFile(
                Path(asset.image.name).name,
                source.read(),
                content_type="image/webp",
            )

        post = publish_feed_post(
            user=publication.creator,
            title=publication.title,
            content=publication.content,
            uploads=[upload],
            is_public=True,
            is_paid=False,
            unlock_price=0,
            on_media_saved=lambda storage, name: (
                saved_files.append((storage, name))
            ),
        )

        media = post.media.filter(
            is_active=True,
        ).first()

        if media is None:
            raise RuntimeError(
                "Published promotional post has no active media."
            )

        if not media.file.storage.exists(media.file.name):
            raise RuntimeError(
                "Published promotional media is missing."
            )

        publication.feed_post = post
        publication.status = ScheduledPublication.STATUS_PUBLISHED
        publication.published_at = timezone.now()
        publication.last_error = ""

        publication.save(
            update_fields=[
                "feed_post",
                "status",
                "published_at",
                "last_error",
                "updated_at",
            ]
        )

        return post
