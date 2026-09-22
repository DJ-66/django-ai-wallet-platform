import hashlib
import json
import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from auctions.models import ScheduledPublication


User = get_user_model()

DEFAULT_SOURCE_ROOT = Path("/creator-packs")

MANIFEST_PATH = (
    Path(settings.BASE_DIR)
    / "auctions"
    / "data"
    / "ai_creator_media_manifest.json"
)

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".avif",
}

CAPTIONS = [
    "A new favorite from the collection. ✨",
    "Fresh from the camera roll. 📸",
    "Adding this one to the collection. 🖤",
    "A little something from today's creative mood.",
    "One more moment worth sharing. ✨",
    "New look, new post, same creative energy.",
    "From the latest collection. 📸",
    "A new addition to my digital world.",
]

RELEASE_INTERVAL = timedelta(hours=24)


def publication_key(account, source_path):
    digest = hashlib.sha256(
        f"{account.lower()}:{source_path}".encode()
    ).hexdigest()[:24]

    return f"ai:{account.lower()}:{digest}"


class Command(BaseCommand):
    help = (
        "Queue one next daily publication for each AI creator. "
        "Initial creator slots are staggered across 24 hours; "
        "subsequent slots extend that creator's queue by 24 hours."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-root",
            default=str(DEFAULT_SOURCE_ROOT),
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=14,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def _load_manifest(self):
        return json.loads(MANIFEST_PATH.read_text())

    def _eligible_files(
        self,
        *,
        source_root,
        creator,
        already_scheduled,
    ):
        reserved = creator.get("avatar_source")
        eligible = []

        for pack_name in creator["packs"]:
            pack = source_root / pack_name

            if not pack.is_dir():
                raise CommandError(
                    f"Creator pack missing: {pack}"
                )

            for path in pack.rglob("*"):
                if not path.is_file():
                    continue

                if path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                relative = str(
                    path.relative_to(source_root)
                )

                if relative == reserved:
                    continue

                if relative in already_scheduled:
                    continue

                eligible.append(relative)

        return sorted(eligible)

    def handle(self, *args, **options):
        source_root = Path(
            options["source_root"]
        ).resolve()

        seed = options["seed"]
        dry_run = options["dry_run"]

        manifest = self._load_manifest()
        creators = manifest["creators"]

        if not creators:
            raise CommandError(
                "AI creator manifest contains no creators."
            )

        now = timezone.now()
        rng = random.Random(seed)

        # Stable initial slot spacing:
        # 24 hours / number of active publishing identities.
        slot_spacing = RELEASE_INTERVAL / len(creators)

        proposals = []

        for slot_index, creator in enumerate(creators):
            account = creator["account"]

            user = User.objects.filter(
                username__iexact=account
            ).first()

            if user is None:
                raise CommandError(
                    f"Manifest account does not exist: @{account}"
                )

            history = (
                ScheduledPublication.objects
                .filter(creator=user)
                .exclude(
                    status=ScheduledPublication.STATUS_FAILED
                )
                .order_by("-scheduled_for")
            )

            latest = history.first()

            already_scheduled = set(
                history.values_list(
                    "source_path",
                    flat=True,
                )
            )

            eligible = self._eligible_files(
                source_root=source_root,
                creator=creator,
                already_scheduled=already_scheduled,
            )

            if not eligible:
                raise CommandError(
                    f"@{account} has no eligible images."
                )

            source_path = rng.choice(eligible)

            if latest is None:
                scheduled_for = (
                    now
                    + slot_spacing * slot_index
                )
            else:
                scheduled_for = max(
                    now,
                    latest.scheduled_for
                    + RELEASE_INTERVAL,
                )

            proposals.append(
                {
                    "creator": user,
                    "account": account,
                    "source_path": source_path,
                    "scheduled_for": scheduled_for,
                    "caption": rng.choice(CAPTIONS),
                }
            )

        self.stdout.write(
            "\n=== AI DAILY PUBLICATION PLAN ==="
        )
        self.stdout.write(
            f"identities={len(creators)} "
            f"interval_hours=24 "
            f"seed={seed}"
        )

        created = 0

        for proposal in proposals:
            account = proposal["account"]
            source_path = proposal["source_path"]
            scheduled_for = proposal["scheduled_for"]

            key = publication_key(
                account,
                source_path,
            )

            self.stdout.write(
                f"{scheduled_for.isoformat()} "
                f"| @{account:<20} "
                f"| {source_path}"
            )

            if dry_run:
                continue

            with transaction.atomic():
                _, was_created = (
                    ScheduledPublication.objects.get_or_create(
                        publication_key=key,
                        defaults={
                            "creator": proposal["creator"],
                            "source_path": source_path,
                            "title": "",
                            "content": proposal["caption"],
                            "scheduled_for": scheduled_for,
                            "status": (
                                ScheduledPublication.STATUS_QUEUED
                            ),
                        },
                    )
                )

            if was_created:
                created += 1

        if dry_run:
            self.stdout.write(
                "\nai_publication_action=dry_run"
            )
            self.stdout.write(
                f"ai_publication_would_create={len(proposals)}"
            )
        else:
            self.stdout.write(
                f"\nai_publication_created={created}"
            )
            self.stdout.write(
                f"ai_publication_requested={len(proposals)}"
            )
