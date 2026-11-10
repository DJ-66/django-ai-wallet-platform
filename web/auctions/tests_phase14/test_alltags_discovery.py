from django.contrib.auth.models import User
from django.test import TestCase

from auctions.alltags_services import purchase_alltags_promotion
from auctions.models import BidWallet, FeedPost, FeedPostMedia, Hashtag
from auctions.services import (
    get_public_hashtag_posts,
    get_public_hashtag_post_count,
)


class AllTagsDiscoveryTests(TestCase):

    def setUp(self):
        self.creator = User.objects.create_user(
            username="AllTagsDiscoveryTest",
            password="test-password",
        )

        BidWallet.objects.create(
            user=self.creator,
            credits=100,
        )

        self.fashion = Hashtag.objects.create(name="fashion")
        self.travel = Hashtag.objects.create(name="travel")

        self.post = FeedPost.objects.create(
            user=self.creator,
            content="Universal discovery test",
            image="feed/discovery-test.webp",
            is_public=True,
            is_paid=False,
        )

        self.post.hashtags.add(self.fashion)

    def test_promotion_reaches_unrelated_hashtags(self):
        self.fashion.refresh_from_db()
        self.travel.refresh_from_db()

        fashion_count_before = self.fashion.usage_count
        travel_count_before = self.travel.usage_count

        purchase_alltags_promotion(
            creator=self.creator,
            post=self.post,
        )

        for tag in (self.fashion, self.travel):
            with self.subTest(tag=tag.name):
                ids = list(
                    get_public_hashtag_posts(tag)
                    .values_list("pk", flat=True)
                )

                self.assertEqual(ids.count(self.post.pk), 1)
                self.assertEqual(
                    get_public_hashtag_post_count(tag),
                    1,
                )

        self.assertEqual(
            list(self.post.hashtags.values_list("name", flat=True)),
            ["fashion"],
        )

        self.fashion.refresh_from_db()
        self.travel.refresh_from_db()

        self.assertEqual(
            self.fashion.usage_count,
            fashion_count_before,
        )
        self.assertEqual(
            self.travel.usage_count,
            travel_count_before,
        )


    def test_private_promoted_post_hidden(self):
        purchase_alltags_promotion(
            creator=self.creator,
            post=self.post,
        )

        self.post.is_public = False
        self.post.save(update_fields=["is_public"])

        self.assertFalse(
            get_public_hashtag_posts(self.travel)
            .filter(pk=self.post.pk)
            .exists()
        )

    def test_paid_promoted_post_hidden(self):
        purchase_alltags_promotion(
            creator=self.creator,
            post=self.post,
        )

        self.post.is_paid = True
        self.post.save(update_fields=["is_paid"])

        self.assertFalse(
            get_public_hashtag_posts(self.travel)
            .filter(pk=self.post.pk)
            .exists()
        )

    def test_removed_image_hides_promotion(self):
        purchase_alltags_promotion(
            creator=self.creator,
            post=self.post,
        )

        self.post.image = ""
        self.post.save(update_fields=["image"])

        self.assertFalse(
            get_public_hashtag_posts(self.travel)
            .filter(pk=self.post.pk)
            .exists()
        )


    def test_forbidden_media_hides_promotion(self):
        purchase_alltags_promotion(
            creator=self.creator,
            post=self.post,
        )

        for media_type in (
            FeedPostMedia.MEDIA_TYPE_VIDEO,
            FeedPostMedia.MEDIA_TYPE_AUDIO,
            FeedPostMedia.MEDIA_TYPE_PDF,
        ):
            with self.subTest(media_type=media_type):
                media = FeedPostMedia.objects.create(
                    post=self.post,
                    file=f"feed/test-{media_type}",
                    media_type=media_type,
                    is_active=True,
                )

                self.assertFalse(
                    get_public_hashtag_posts(self.travel)
                    .filter(pk=self.post.pk)
                    .exists()
                )

                media.delete()
