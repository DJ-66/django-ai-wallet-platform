import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError

from auctions.ai_services.creator_copy import (
    generate_creator_post_copy,
)
from auctions.management.commands.generate_ai_publications import (
    MANIFEST_PATH,
)
from auctions.models import (
    FeedPostMedia,
    ScheduledPublication,
)
from auctions.post_localization import (
    LocalizationOllamaProvider,
    _translate_target,
)


GENERIC_TITLES = {
    "Today's Mood ✨",
    "Fresh Look 📸",
    "A New Favorite 🖤",
    "Creative Energy ✨",
    "From the Collection",
    "Today's Look",
    "New Drop ✨",
    "Camera Roll Favorite 📸",
    "A Little Something New",
    "Current Mood 🖤",
    "Latest Favorite",
    "New From My World ✨",
}

GENERIC_CAPTIONS = {
    "A new favorite from the collection.",
    "Fresh from the camera roll. 📸",
    "Adding this one to the collection. 🖤",
    "A little something from today's creative mood.",
    "One more moment worth sharing. ✨",
    "New look, new post, same creative energy.",
    "From the latest collection. 📸",
    "A new addition to my digital world.",
    "Sharing another favorite today. ✨",
    "This one deserved a spot on the feed.",
    "A little glimpse from the latest set.",
    "Another moment from behind the scenes. 📸",
}


def validate_recovery_translations(translations, hashtags):
    """Reject incomplete or inconsistent recovery copy."""
    import re

    expected = [f"#{tag}" for tag in hashtags]

    if len(expected) != 6 or len(set(expected)) != 6:
        raise CommandError(
            "Recovery requires six unique hashtags."
        )

    for language in ("en", "es", "pt"):
        data = translations.get(language)

        if not isinstance(data, dict):
            raise CommandError(
                f"Missing {language} translation."
            )

        title = data.get("title")
        content = data.get("content")

        if (
            not isinstance(title, str)
            or not title.strip()
            or len(title) > 120
        ):
            raise CommandError(
                f"Invalid {language} title."
            )

        if (
            not isinstance(content, str)
            or not content.strip()
            or len(content) > 2500
        ):
            raise CommandError(
                f"Invalid {language} content."
            )

        actual = re.findall(
            r"(?<![\\w#])#[A-Za-z0-9_]+",
            content,
        )

        if sorted(actual) != sorted(expected):
            raise CommandError(
                f"{language} hashtags were not preserved."
            )

        separator = chr(10) * 2
        literal_escape = chr(92) + "n"

        if (
            content.count(separator) != 1
            or literal_escape in content
        ):
            raise CommandError(
                f"Invalid {language} paragraph formatting."
            )

        caption, hashtag_line = content.split(separator)

        if not caption.strip():
            raise CommandError(
                f"Missing {language} caption."
            )

        if hashtag_line.strip().split() != expected:
            raise CommandError(
                f"Invalid {language} hashtag line."
            )



class Command(BaseCommand):
    help = "Preview creator caption recovery without database writes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--publication-id",
            type=int,
            required=True,
        )
        parser.add_argument(
            "--source-root",
            default="/creator-packs",
        )

    def handle(self, *args, **options):
        publication = (
            ScheduledPublication.objects
            .select_related("creator", "feed_post")
            .get(pk=options["publication_id"])
        )

        original_caption = (
            publication.content.split("\n\n")[0].strip()
        )

        if (
            publication.title not in GENERIC_TITLES
            and original_caption not in GENERIC_CAPTIONS
        ):
            raise CommandError(
                "Publication does not contain generic creator copy."
            )

        manifest = json.loads(
            Path(MANIFEST_PATH).read_text()
        )

        creator = next(
            (
                item for item in manifest["creators"]
                if item["account"].lower()
                == publication.creator.username.lower()
            ),
            None,
        )

        if creator is None:
            raise CommandError(
                "Creator not found in manifest."
            )

        hashtag_pool = creator["post_style"]["hashtags"]

        identity_tag = next(
            (
                tag
                for preferred in ("AIInfluencer", "DigitalCreator")
                for tag in hashtag_pool
                if tag.lower() == preferred.lower()
            ),
            hashtag_pool[0],
        )

        approved = [
            tag for tag in hashtag_pool
            if tag.lower() != identity_tag.lower()
        ]

        if publication.status == "published":
            if (
                publication.feed_post_id is None
                or publication.feed_post.user_id
                != publication.creator_id
            ):
                raise CommandError(
                    "Published post ownership mismatch."
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
                raise CommandError("Published image missing.")

            image_field = media.file

        elif publication.status == "queued":
            image_field = None

        else:
            raise CommandError(
                "Unsupported publication status."
            )

        with tempfile.TemporaryDirectory() as directory:
            if image_field is not None:
                suffix = Path(image_field.name).suffix or ".jpg"
                image_path = Path(directory) / ("source" + suffix)

                with image_field.open("rb") as source:
                    image_path.write_bytes(source.read())
            else:
                source_root = Path(
                    options["source_root"]
                ).resolve()

                image_path = (
                    source_root
                    / publication.source_path
                ).resolve()

                if not image_path.is_relative_to(source_root):
                    raise CommandError(
                        "Source image escapes creator media root."
                    )

            if not image_path.is_file():
                raise CommandError("Source image missing.")

            generated = generate_creator_post_copy(
                image_path=image_path,
                account=creator["account"],
                bio=creator.get("bio", ""),
                approved_hashtags=approved,
            )

        if len(generated["hashtags"]) != 4:
            raise CommandError(
                "Creator AI must return four hashtags."
            )

        hashtags = (
            generated["hashtags"]
            + [identity_tag, "FANZ"]
        )

        content = (
            generated["caption"]
            + "\n\n"
            + " ".join(f"#{tag}" for tag in hashtags)
        )

        english = {
            "title": generated["title"],
            "content": content,
        }

        sample = SimpleNamespace(**english)
        provider = LocalizationOllamaProvider()

        translations = {
            "en": english,
        }

        for language in ("es", "pt"):
            translations[language] = _translate_target(
                sample,
                source_language="en",
                target_language=language,
                provider=provider,
                attempts=1,
            )

        validate_recovery_translations(
            translations,
            hashtags,
        )

        self.stdout.write(
            "\n=== CREATOR CAPTION RECOVERY PREVIEW ==="
        )
        self.stdout.write(
            f"PUBLICATION: {publication.pk}"
        )
        self.stdout.write(
            f"CREATOR: @{publication.creator.username}"
        )
        self.stdout.write(
            f"STATUS: {publication.status}"
        )

        for language, data in translations.items():
            self.stdout.write(f"\nLANGUAGE: {language}")
            self.stdout.write(f"TITLE: {data['title']}")
            self.stdout.write(f"CONTENT: {data['content']}")

        self.stdout.write(
            "\nPREVIEW COMPLETE — NO DATABASE WRITES"
        )
