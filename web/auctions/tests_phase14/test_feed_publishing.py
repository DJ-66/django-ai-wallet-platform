from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from PIL import Image

from auctions.feed_publishing import publish_feed_post
from auctions.models import FeedPost, FeedPostMedia


User = get_user_model()


def make_jpeg(name="test.jpg"):
    output = BytesIO()

    Image.new(
        "RGB",
        (640, 800),
        (120, 140, 160),
    ).save(
        output,
        format="JPEG",
        quality=90,
    )

    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type="image/jpeg",
    )


class PublishFeedPostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="phase14creator",
            password="test-password",
        )

    def test_publishes_free_image_post_as_webp(self):
        post = publish_feed_post(
            user=self.user,
            title="  Test title  ",
            content="  Test content  ",
            uploads=[make_jpeg()],
            is_public=True,
            is_paid=False,
            unlock_price=999,
        )

        post.refresh_from_db()

        self.assertEqual(post.user, self.user)
        self.assertEqual(post.title, "Test title")
        self.assertEqual(post.content, "Test content")
        self.assertTrue(post.is_public)
        self.assertFalse(post.is_paid)
        self.assertEqual(post.unlock_price, 0)

        media = post.media.get()

        self.assertEqual(
            media.media_type,
            FeedPostMedia.MEDIA_TYPE_IMAGE,
        )
        self.assertTrue(media.is_active)
        self.assertEqual(media.display_order, 0)
        self.assertTrue(media.file.name.endswith(".webp"))
        self.assertTrue(media.file.storage.exists(media.file.name))

    def test_paid_post_is_private_and_has_minimum_unlock(self):
        post = publish_feed_post(
            user=self.user,
            title="Premium",
            content="Premium content",
            uploads=[make_jpeg("premium.jpg")],
            is_public=True,
            is_paid=True,
            unlock_price=0,
        )

        post.refresh_from_db()

        self.assertTrue(post.is_paid)
        self.assertFalse(post.is_public)
        self.assertEqual(post.unlock_price, 1)

    def test_invalid_image_does_not_create_post(self):
        bad_upload = SimpleUploadedFile(
            "bad.jpg",
            b"not-an-image",
            content_type="image/jpeg",
        )

        with self.assertRaises(ValidationError):
            publish_feed_post(
                user=self.user,
                content="Should fail",
                uploads=[bad_upload],
            )

        self.assertEqual(
            FeedPost.objects.filter(user=self.user).count(),
            0,
        )


class ScheduledPublicationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="scheduledcreator",
            password="test-password",
        )

    def test_publication_key_is_unique(self):
        from django.db import IntegrityError
        from django.utils import timezone

        from auctions.models import ScheduledPublication

        ScheduledPublication.objects.create(
            publication_key="scheduled-test-1",
            creator=self.user,
            source_path="Creator Pack/image-1.jpg",
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_QUEUED,
        )

        with self.assertRaises(IntegrityError):
            ScheduledPublication.objects.create(
                publication_key="scheduled-test-1",
                creator=self.user,
                source_path="Creator Pack/image-2.jpg",
                scheduled_for=timezone.now(),
                status=ScheduledPublication.STATUS_QUEUED,
            )

    def test_published_requires_feed_post_and_timestamp(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        from auctions.models import ScheduledPublication

        publication = ScheduledPublication(
            publication_key="scheduled-test-2",
            creator=self.user,
            source_path="Creator Pack/image.jpg",
            scheduled_for=timezone.now(),
            status=ScheduledPublication.STATUS_PUBLISHED,
        )

        with self.assertRaises(ValidationError):
            publication.validate_constraints()
