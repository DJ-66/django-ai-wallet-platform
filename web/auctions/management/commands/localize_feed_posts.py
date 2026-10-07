from django.core.management.base import BaseCommand

from auctions.models import FeedPost
from auctions.post_localization import (
    PostLocalizationError,
    localize_feed_post,
)


class Command(BaseCommand):
    help = (
        "Populate missing EN/ES/PT localizations for FANZ feed posts. "
        "Existing complete translations are preserved."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
        )
        parser.add_argument(
            "--post-id",
            type=int,
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = max(1, options["limit"])
        post_id = options.get("post_id")

        posts = (
            FeedPost.objects
            .filter(is_public=True)
            .prefetch_related("translations")
            .order_by("-created_at", "-pk")
        )

        if post_id:
            posts = posts.filter(pk=post_id)

        scanned = 0
        localized = 0
        complete = 0
        failed = 0

        for post in posts.iterator(
            chunk_size=100,
        ):
            if scanned >= limit:
                break

            existing = {
                row.language
                for row in post.translations.all()
                if row.title.strip()
                and row.content.strip()
            }

            scanned += 1

            self.stdout.write(
                f"POST {post.pk} @{post.user.username} "
                f"existing={sorted(existing)}"
            )

            try:
                result = localize_feed_post(
                    post,
                    dry_run=dry_run,
                )
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"POST {post.pk} FAILED: {exc}"
                    )
                )
                continue

            if result["status"] == "complete":
                complete += 1
                continue

            localized += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"POST {post.pk} "
                    f"source={result['source_language']} "
                    f"{'would_create' if dry_run else 'created'}="
                    f"{result['created']}"
                )
            )

        self.stdout.write("")
        self.stdout.write(
            f"scanned: {scanned}"
        )
        self.stdout.write(
            f"localized: {localized}"
        )
        self.stdout.write(
            f"already_complete: {complete}"
        )
        self.stdout.write(
            f"failed: {failed}"
        )
        self.stdout.write(
            "mode: DRY RUN"
            if dry_run
            else "mode: EXECUTE"
        )
