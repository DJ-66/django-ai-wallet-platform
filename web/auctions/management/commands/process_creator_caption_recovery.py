import json
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from auctions.ai_services.creator_caption_recovery import (
    claim_next_publication,
    verify_claim,
    apply_recovery,
    mark_recovery_failed,
)
from auctions.ai_services.creator_recovery_generation import (
    generate_recovery_translations,
)
from auctions.management.commands.generate_ai_publications import (
    MANIFEST_PATH,
)
from auctions.models import FeedPostMedia, ScheduledPublication


class Command(BaseCommand):
    help = "Recover one generic AI creator caption."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-root",
            default="/creator-packs",
        )
        parser.add_argument(
            "--scope",
            choices=("queued", "published"),
            default="queued",
        )

    def handle(self, *args, **options):
        scope = options["scope"]

        claim = claim_next_publication(
            lease_minutes=30,
            queued_only=(scope == "queued"),
            published_only=(scope == "published"),
            min_lead_minutes=45 if scope == "queued" else 0,
        )

        if claim is None:
            self.stdout.write(
                "creator_caption_recovery_due=none"
            )
            return

        publication_id, token = claim

        try:
            publication = (
                ScheduledPublication.objects
                .select_related("creator", "feed_post")
                .get(pk=publication_id)
            )

            expected_status = (
                ScheduledPublication.STATUS_QUEUED
                if scope == "queued"
                else ScheduledPublication.STATUS_PUBLISHED
            )

            if publication.status != expected_status:
                raise CommandError(
                    "Publication status does not match recovery scope."
                )

            expected_title = publication.title
            expected_content = publication.content

            manifest = json.loads(
                Path(MANIFEST_PATH).read_text()
            )

            creator = next(
                (
                    item
                    for item in manifest["creators"]
                    if item["account"].casefold()
                    == publication.creator.username.casefold()
                ),
                None,
            )

            if creator is None:
                raise CommandError(
                    "Creator missing from manifest."
                )

            expected_media_id = None
            expected_media_name = None

            with tempfile.TemporaryDirectory() as directory:
                if scope == "published":
                    if publication.feed_post_id is None:
                        raise CommandError(
                            "Published publication has no FeedPost."
                        )

                    if not publication.feed_post or (
                        publication.feed_post.user_id
                        != publication.creator_id
                    ):
                        raise CommandError(
                            "Published FeedPost ownership mismatch."
                        )

                    media = (
                        FeedPostMedia.objects
                        .filter(
                            post_id=publication.feed_post_id,
                            media_type=FeedPostMedia.MEDIA_TYPE_IMAGE,
                            is_active=True,
                        )
                        .order_by("display_order", "pk")
                        .first()
                    )

                    if media is None:
                        raise CommandError(
                            "Published image missing."
                        )

                    expected_media_id = media.pk
                    expected_media_name = media.file.name

                    suffix = Path(media.file.name).suffix or ".jpg"
                    image_path = Path(directory) / ("source" + suffix)

                    with media.file.open("rb") as source:
                        image_path.write_bytes(source.read())
                else:
                    source_root = Path(
                        options["source_root"]
                    ).resolve()

                    image_path = (
                        source_root / publication.source_path
                    ).resolve()

                    if not image_path.is_relative_to(source_root):
                        raise CommandError(
                            "Image escapes creator root."
                        )

                    if not image_path.is_file():
                        raise CommandError(
                            "Creator image missing."
                        )

                translations, hashtags = (
                    generate_recovery_translations(
                        image_path=image_path,
                        creator=creator,
                    )
                )

            if not verify_claim(publication_id, token):
                raise CommandError(
                    "Recovery claim expired."
                )

            result = apply_recovery(
                publication_id,
                token,
                translations,
                hashtags,
                expected_title=expected_title,
                expected_content=expected_content,
                min_lead_minutes=5 if scope == "queued" else 0,
                expected_media_id=expected_media_id,
                expected_media_name=expected_media_name,
            )

            self.stdout.write(
                "creator_caption_recovery_completed="
                + str(result["publication_id"])
            )

        except Exception as exc:
            mark_recovery_failed(
                publication_id,
                token,
                str(exc),
            )
            self.stderr.write(
                f"creator_caption_recovery_failed={publication_id}"
            )
            raise
