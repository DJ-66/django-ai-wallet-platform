import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from PIL import Image

from auctions.models import (
    ScheduledPublication,
    FeedPost,
    FeedPostMedia,
    FeedPostTranslation,
)
from auctions.management.commands import repair_creator_captions


User = get_user_model()


class CreatorCaptionRecoveryPreviewTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.root = Path(self.tempdir.name)
        self.image = self.root / "creator.jpg"

        Image.new(
            "RGB", (320, 480), (100, 120, 150)
        ).save(self.image)

        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({
            "creators": [{
                "account": "TestCreator",
                "bio": "Playful fictional creator.",
                "post_style": {
                    "hashtags": [
                        "AIInfluencer",
                        "Fashion",
                        "Lifestyle",
                        "Style",
                        "DigitalCreator",
                        "Confidence",
                    ],
                },
            }],
        }))

        self.user = User.objects.create_user(
            username="TestCreator",
            password="test-password",
        )

        self.publication = ScheduledPublication.objects.create(
            publication_key="ai:testcreator:preview",
            creator=self.user,
            source_path="creator.jpg",
            scheduled_for=timezone.now(),
            title="From the Collection",
            content=(
                "A new favorite from the collection."
                "\\n\\n#Fashion #FANZ"
            ),
            status=ScheduledPublication.STATUS_QUEUED,
        )

    def test_preview_does_not_modify_publication(self):
        original_title = self.publication.title
        original_content = self.publication.content

        with (
            patch.object(
                repair_creator_captions,
                "MANIFEST_PATH",
                self.manifest,
            ),
            patch.object(
                repair_creator_captions,
                "generate_creator_post_copy",
                return_value={
                    "title": "Coffee and Chaos",
                    "caption": "One espresso became three.",
                    "hashtags": [
                        "Fashion",
                        "Lifestyle",
                        "Style",
                        "Confidence",
                    ],
                },
            ) as generate,
            patch.object(
                repair_creator_captions,
                "_translate_target",
                side_effect=[
                    {
                        "title": "Café y caos",
                        "content": 'Un café se convirtió en tres.\n\n#Fashion #Lifestyle #Style #Confidence #AIInfluencer #FANZ'                    },
                    {
                        "title": "Café e caos",
                        "content": 'Um café virou três.\n\n#Fashion #Lifestyle #Style #Confidence #AIInfluencer #FANZ'                    },
                ],
            ) as translate,
        ):
            call_command(
                "repair_creator_captions",
                publication_id=self.publication.pk,
                source_root=str(self.root),
            )

        self.publication.refresh_from_db()

        self.assertEqual(
            self.publication.title,
            original_title,
        )
        self.assertEqual(
            self.publication.content,
            original_content,
        )

        self.assertEqual(generate.call_count, 1)
        self.assertEqual(translate.call_count, 2)

    def test_published_preview_preserves_records(self):
        from django.core.files.base import ContentFile
        from django.test import override_settings

        with override_settings(MEDIA_ROOT=self.root):
            feed = FeedPost.objects.create(
                user=self.user,
                title="From the Collection",
                content="A new favorite from the collection.",
            )

            media = FeedPostMedia.objects.create(
                post=feed,
                media_type=FeedPostMedia.MEDIA_TYPE_IMAGE,
                is_active=True,
            )

            media.file.save(
                "recovery-test.jpg",
                ContentFile(self.image.read_bytes()),
                save=True,
            )

            self.addCleanup(
                lambda: media.file.storage.delete(
                    media.file.name
                )
            )

            original_media_name = media.file.name

            translations = {}

            for language in ("en", "es", "pt"):
                translations[language] = (
                    FeedPostTranslation.objects.create(
                        post=feed,
                        language=language,
                        title="From the Collection",
                        content="Original generic caption.",
                    )
                )

            self.publication.status = (
                ScheduledPublication.STATUS_PUBLISHED
            )
            self.publication.feed_post = feed
            self.publication.published_at = timezone.now()
            self.publication.save(
                update_fields=[
                    "status",
                    "feed_post",
                    "published_at",
                ]
            )

            hashtags = (
                "#Fashion #Lifestyle #Style "
                "#Confidence #AIInfluencer #FANZ"
            )

            with (
                patch.object(
                    repair_creator_captions,
                    "MANIFEST_PATH",
                    self.manifest,
                ),
                patch.object(
                    repair_creator_captions,
                    "generate_creator_post_copy",
                    return_value={
                        "title": "Coffee and Chaos",
                        "caption": "One espresso became three.",
                        "hashtags": [
                            "Fashion",
                            "Lifestyle",
                            "Style",
                            "Confidence",
                        ],
                    },
                ) as generate,
                patch.object(
                    repair_creator_captions,
                    "_translate_target",
                    side_effect=[
                        {
                            "title": "Café y caos",
                            "content": (
                                "Un café se convirtió en tres."
                                + chr(10) * 2 + hashtags
                            ),
                        },
                        {
                            "title": "Café e caos",
                            "content": (
                                "Um café virou três."
                                + chr(10) * 2 + hashtags
                            ),
                        },
                    ],
                ) as translate,
            ):
                call_command(
                    "repair_creator_captions",
                    publication_id=self.publication.pk,
                )

            self.publication.refresh_from_db()
            feed.refresh_from_db()
            media.refresh_from_db()

            self.assertEqual(
                self.publication.title,
                "From the Collection",
            )
            self.assertEqual(
                feed.title,
                "From the Collection",
            )
            self.assertEqual(
                feed.content,
                "A new favorite from the collection.",
            )
            self.assertEqual(
                media.file.name,
                original_media_name,
            )

            for translation in translations.values():
                translation.refresh_from_db()
                self.assertEqual(
                    translation.title,
                    "From the Collection",
                )
                self.assertEqual(
                    translation.content,
                    "Original generic caption.",
                )

            self.assertEqual(generate.call_count, 1)
            self.assertEqual(translate.call_count, 2)

    def test_non_generic_publication_rejected(self):
        self.publication.title = "An Original Story"
        self.publication.content = "A personal caption."
        self.publication.save()

        with self.assertRaises(CommandError):
            call_command(
                "repair_creator_captions",
                publication_id=self.publication.pk,
            )
