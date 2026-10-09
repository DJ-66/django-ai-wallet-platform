from django.core.management.base import BaseCommand
from datetime import timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

from auctions.localization_fingerprint import localization_fingerprint
from auctions.models import FeedPost, FeedPostLocalizationState
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
            "--status",
            action="store_true",
            help="Show localization backlog without processing posts.",
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

    def show_status(self):
        now = timezone.now()

        posts = (
            FeedPost.objects
            .filter(is_public=True)
            .annotate(
                complete_language_count=Count(
                    "translations",
                    filter=(
                        Q(
                            translations__language__in=[
                                "en", "es", "pt"
                            ]
                        )
                        & ~Q(translations__title="")
                        & ~Q(translations__content="")
                    ),
                    distinct=True,
                )
            )
            .annotate(
                source_copy_count=Count(
                    "translations",
                    filter=Q(
                        translations__language__in=[
                            "en", "es", "pt"
                        ],
                        translations__title=F("title"),
                        translations__content=F("content"),
                    ),
                    distinct=True,
                )
            )
        )

        total = posts.count()

        complete = posts.filter(
            complete_language_count=3,
        ).count()

        incomplete = posts.filter(
            complete_language_count__lt=3,
        ).count()

        suspicious = posts.filter(
            source_copy_count__gte=2,
        ).count()

        cooldown = posts.filter(
            localization_state__next_retry_at__gt=now,
        ).count()

        self.stdout.write(
            "\n=== FANZ LOCALIZATION STATUS ==="
        )
        self.stdout.write(f"public_posts: {total}")
        self.stdout.write(f"complete_3_of_3: {complete}")
        self.stdout.write(f"incomplete: {incomplete}")
        self.stdout.write(
            f"suspected_source_copies: {suspicious}"
        )
        self.stdout.write(
            f"retry_cooldown: {cooldown}"
        )

        percentage = (
            100 * complete / total
            if total else 100
        )

        self.stdout.write(
            f"completion_percentage: {percentage:.1f}%"
        )
        self.stdout.write("mode: STATUS ONLY")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = max(1, options["limit"])

        if options["status"]:
            self.show_status()
            return
        post_id = options.get("post_id")

        now = timezone.now()

        posts = (
            FeedPost.objects
            .filter(is_public=True)
            .prefetch_related("translations")
        )

        if not dry_run and not post_id:
            posts = posts.filter(
                Q(localization_state__isnull=True)
                | Q(localization_state__next_retry_at__isnull=True)
                | Q(localization_state__next_retry_at__lte=now)
            )

        if post_id:
            posts = posts.filter(pk=post_id)
        else:
            posts = (
                posts
                .annotate(
                    complete_language_count=Count(
                        "translations",
                        filter=(
                            Q(
                                translations__language__in=[
                                    "en", "es", "pt"
                                ]
                            )
                            & ~Q(translations__title="")
                            & ~Q(translations__content="")
                        ),
                        distinct=True,
                    )
                )
                .annotate(
                    source_copy_count=Count(
                        "translations",
                        filter=Q(
                            translations__language__in=[
                                "en", "es", "pt"
                            ],
                            translations__title=F("title"),
                            translations__content=F("content"),
                        ),
                        distinct=True,
                    )
                )
                .filter(
                    Q(complete_language_count__lt=3)
                    | Q(source_copy_count__gte=2)
                    | (
                        Q(localization_state__isnull=False)
                        & ~Q(localization_state__audited_fingerprint="")
                    )
                )
            )

        def needs_audit(post):
            if getattr(post, "complete_language_count", 0) < 3:
                return True

            try:
                state = post.localization_state
            except FeedPostLocalizationState.DoesNotExist:
                return True

            return not (
                state.audited_fingerprint
                and state.audited_fingerprint
                == localization_fingerprint(
                    post,
                    translations=post.translations.all(),
                )
            )

        if post_id:
            selected_posts = list(
                posts.order_by("-created_at", "-pk")[:1]
            )
        else:
            # Scan candidates in both directions until the
            # requested number of eligible posts is collected.
            # Reserve one slot for eligible retries when
            # processing more than one post.
            retry_slots = 1 if limit > 1 else 0
            fresh_capacity = limit - retry_slots

            newest_slots = (fresh_capacity + 1) // 2
            oldest_slots = fresh_capacity - newest_slots

            selected_posts = []
            selected_ids = set()

            def collect(queryset, target, *, retry=False):
                for post in queryset.iterator(chunk_size=100):
                    if len(selected_posts) >= target:
                        break

                    if post.pk in selected_ids:
                        continue

                    try:
                        state = post.localization_state
                    except FeedPostLocalizationState.DoesNotExist:
                        state = None

                    has_failures = bool(
                        state and state.attempt_count > 0
                    )

                    if has_failures != retry:
                        continue

                    if not needs_audit(post):
                        continue

                    selected_posts.append(post)
                    selected_ids.add(post.pk)

            # First: newest and oldest unattempted posts.
            collect(
                posts.order_by("-created_at", "-pk"),
                newest_slots,
            )

            collect(
                posts.order_by("created_at", "pk"),
                fresh_capacity,
            )

            # Fill unused fresh capacity.
            if len(selected_posts) < fresh_capacity:
                collect(
                    posts.order_by("-created_at", "-pk"),
                    fresh_capacity,
                )

            # Reserve an opportunity for eligible retries.
            if retry_slots:
                collect(
                    posts.order_by(
                        "localization_state__last_attempt_at",
                        "created_at",
                        "pk",
                    ),
                    limit,
                    retry=True,
                )

            # Return unused retry capacity to fresh posts.
            if len(selected_posts) < limit:
                collect(
                    posts.order_by("-created_at", "-pk"),
                    limit,
                )

            # With limit=1, retries run when no fresh post
            # is available. Also fills any remaining capacity.
            if len(selected_posts) < limit:
                collect(
                    posts.order_by(
                        "localization_state__last_attempt_at",
                        "created_at",
                        "pk",
                    ),
                    limit,
                    retry=True,
                )

        scanned = 0
        localized = 0
        complete = 0
        failed = 0

        for post in selected_posts:
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

                if not dry_run:
                    state, _ = (
                        FeedPostLocalizationState.objects
                        .get_or_create(post=post)
                    )

                    state.attempt_count += 1

                    delay_minutes = min(
                        30 * (2 ** min(
                            state.attempt_count - 1,
                            10,
                        )),
                        1440,
                    )

                    state.last_error = str(exc)[:4000]
                    state.last_attempt_at = timezone.now()
                    state.next_retry_at = (
                        state.last_attempt_at
                        + timedelta(minutes=delay_minutes)
                    )

                    state.save()

                self.stderr.write(
                    self.style.ERROR(
                        f"POST {post.pk} FAILED: {exc}"
                    )
                )
                continue

            if not dry_run:
                state, _ = (
                    FeedPostLocalizationState.objects
                    .get_or_create(post=post)
                )

                state.attempt_count = 0
                state.last_error = ""
                state.last_attempt_at = timezone.now()
                state.next_retry_at = None

                # Calculate after localization writes translations.
                post.refresh_from_db(
                    fields=["title", "content"]
                )
                state.audited_fingerprint = (
                    localization_fingerprint(post)
                )

                state.save()

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
