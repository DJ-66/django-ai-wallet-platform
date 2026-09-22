import json
import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from auctions.feed_publishing import publish_feed_post
from auctions.models import ScheduledPublication


DEFAULT_SOURCE_ROOT = Path("/home/dj/fanz-content/creator-packs")
MANIFEST_PATH = (
    Path(settings.BASE_DIR)
    / "auctions"
    / "data"
    / "ai_creator_media_manifest.json"
)


class Command(BaseCommand):
    help = "Publish the next due queued FANZ publication."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-root",
            default=str(DEFAULT_SOURCE_ROOT),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def _reserved_avatar_paths(self):
        data = json.loads(MANIFEST_PATH.read_text())

        return {
            creator["avatar_source"]
            for creator in data["creators"]
            if creator.get("avatar_source")
        }

    def _resolve_source(self, source_root, relative_path):
        root = source_root.resolve()
        source = (root / relative_path).resolve()

        try:
            source.relative_to(root)
        except ValueError as exc:
            raise CommandError(
                "Scheduled source path escapes creator source root."
            ) from exc

        return source

    def _claim_next(self):
        now = timezone.now()

        with transaction.atomic():
            publication = (
                ScheduledPublication.objects
                .select_for_update(skip_locked=True)
                .filter(
                    status=ScheduledPublication.STATUS_QUEUED,
                    scheduled_for__lte=now,
                )
                .order_by(
                    "scheduled_for",
                    "id",
                )
                .first()
            )

            if publication is None:
                return None

            publication.status = (
                ScheduledPublication.STATUS_PUBLISHING
            )
            publication.attempt_count += 1
            publication.last_error = ""
            publication.save(
                update_fields=[
                    "status",
                    "attempt_count",
                    "last_error",
                    "updated_at",
                ]
            )

            return publication.pk

    def _mark_failed(self, publication_id, message):
        ScheduledPublication.objects.filter(
            pk=publication_id
        ).update(
            status=ScheduledPublication.STATUS_FAILED,
            last_error=str(message)[:4000],
            updated_at=timezone.now(),
        )

    def handle(self, *args, **options):
        source_root = Path(options["source_root"])
        dry_run = options["dry_run"]

        publication_id = self._claim_next()

        if publication_id is None:
            self.stdout.write("scheduled_publication_due=none")
            return

        publication = (
            ScheduledPublication.objects
            .select_related("creator")
            .get(pk=publication_id)
        )

        source = self._resolve_source(
            source_root,
            publication.source_path,
        )

        self.stdout.write(
            f"scheduled_publication_id={publication.id}"
        )
        self.stdout.write(
            f"scheduled_publication_key="
            f"{publication.publication_key}"
        )
        self.stdout.write(
            f"scheduled_publication_creator="
            f"@{publication.creator.username}"
        )
        self.stdout.write(
            f"scheduled_publication_source={source}"
        )

        if dry_run:
            ScheduledPublication.objects.filter(
                pk=publication.id
            ).update(
                status=ScheduledPublication.STATUS_QUEUED,
                attempt_count=max(
                    publication.attempt_count - 1,
                    0,
                ),
                updated_at=timezone.now(),
            )

            self.stdout.write(
                "scheduled_publication_action=would_publish"
            )
            return

        reserved = self._reserved_avatar_paths()

        if publication.source_path in reserved:
            message = (
                "Scheduled source is reserved as a creator avatar."
            )
            self._mark_failed(publication.id, message)
            raise CommandError(message)

        if not source.is_file():
            message = f"Scheduled source file does not exist: {source}"
            self._mark_failed(publication.id, message)
            raise CommandError(message)

        try:
            content_type = (
                mimetypes.guess_type(source.name)[0]
                or "application/octet-stream"
            )

            with source.open("rb") as fh:
                upload = SimpleUploadedFile(
                    source.name,
                    fh.read(),
                    content_type=content_type,
                )

            post = publish_feed_post(
                user=publication.creator,
                title=publication.title,
                content=publication.content,
                uploads=[upload],
                is_public=True,
                is_paid=False,
                unlock_price=0,
            )

            media = post.media.filter(
                is_active=True,
            ).first()

            if media is None:
                raise RuntimeError(
                    "Published post has no active media."
                )

            if not media.file.storage.exists(media.file.name):
                raise RuntimeError(
                    "Published media is missing from storage."
                )

            with transaction.atomic():
                locked = (
                    ScheduledPublication.objects
                    .select_for_update()
                    .get(pk=publication.id)
                )

                if (
                    locked.status
                    != ScheduledPublication.STATUS_PUBLISHING
                ):
                    raise RuntimeError(
                        "Publication state changed during publish."
                    )

                locked.feed_post = post
                locked.status = (
                    ScheduledPublication.STATUS_PUBLISHED
                )
                locked.published_at = timezone.now()
                locked.last_error = ""
                locked.save(
                    update_fields=[
                        "feed_post",
                        "status",
                        "published_at",
                        "last_error",
                        "updated_at",
                    ]
                )

            # Database publication is committed before consuming the
            # working-copy source asset. Windows remains the master.
            source.unlink()

            self.stdout.write(
                self.style.SUCCESS(
                    f"scheduled_publication_post={post.pk}"
                )
            )
            self.stdout.write(
                "scheduled_publication_source_consumed=true"
            )

        except Exception as exc:
            current = ScheduledPublication.objects.get(
                pk=publication.id
            )

            # Do not overwrite a successfully committed publication
            # merely because source cleanup failed afterward.
            if (
                current.status
                != ScheduledPublication.STATUS_PUBLISHED
            ):
                self._mark_failed(
                    publication.id,
                    f"{type(exc).__name__}: {exc}",
                )

            raise
