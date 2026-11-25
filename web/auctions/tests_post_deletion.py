import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.utils import timezone

from auctions.models import (
    CreatorPublishingAttempt,
    FeedPost,
    FeedPostMedia,
    Hashtag,
    LegacyAIPublicationLease,
    ScheduledPublication,
)
from auctions.views import (
    add_post_comment,
    delete_feed_post,
    post_detail,
    toggle_pin_post,
    toggle_post_like,
    translate_post,
    unlock_feed_post,
)


class FeedPostDeletionTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username="deletion_owner"
        )
        self.other = User.objects.create_user(
            username="deletion_other"
        )
        self.factory = RequestFactory()

    def make_post(self, **kwargs):
        values = {
            "user": self.owner,
            "title": "Deletion fixture",
            "content": "Regression fixture",
            "is_public": True,
        }
        values.update(kwargs)
        return FeedPost.objects.create(**values)

    def request(self, user=None, method="post"):
        request = getattr(self.factory, method)("/")
        request.user = user or self.owner
        return request

    def delete(self, post, user=None):
        return delete_feed_post(
            self.request(user),
            post.pk,
        )

    def test_ordinary_post_deletion(self):
        post = self.make_post(is_pinned=True)

        self.assertEqual(
            self.delete(post).status_code, 302
        )

        self.assertFalse(
            FeedPost.objects.filter(pk=post.pk).exists()
        )

        historical = FeedPost.all_objects.get(pk=post.pk)

        self.assertIsNotNone(historical.deleted_at)
        self.assertFalse(historical.is_public)
        self.assertFalse(historical.is_pinned)

    def test_unauthorized_deletion(self):
        post = self.make_post()

        with self.assertRaises(Http404):
            self.delete(post, self.other)

        self.assertTrue(
            FeedPost.objects.filter(pk=post.pk).exists()
        )

    def test_get_cannot_delete_post(self):
        post = self.make_post()

        response = delete_feed_post(
            self.request(method="get"),
            post.pk,
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            FeedPost.objects.filter(pk=post.pk).exists()
        )

    def test_repeated_deletion_is_idempotent(self):
        post = self.make_post()

        self.delete(post)

        original = FeedPost.all_objects.get(
            pk=post.pk
        ).deleted_at

        self.assertEqual(
            self.delete(post).status_code, 302
        )

        self.assertEqual(
            FeedPost.all_objects.get(
                pk=post.pk
            ).deleted_at,
            original,
        )

    def test_paid_post_preserved(self):
        post = self.make_post(
            is_paid=True,
            is_public=False,
            unlock_price=10,
        )

        self.assertEqual(
            self.delete(post).status_code, 409
        )

        post.refresh_from_db()

        self.assertIsNone(post.deleted_at)
        self.assertTrue(post.is_paid)
        self.assertEqual(post.unlock_price, 10)

    def test_media_deactivated_but_record_retained(self):
        post = self.make_post()

        media = FeedPostMedia.objects.create(
            post=post,
            file="feed/media/deletion-fixture.webp",
            media_type="image",
            is_active=True,
        )

        self.delete(post)

        media.refresh_from_db()

        self.assertFalse(media.is_active)
        self.assertEqual(media.post_id, post.pk)
        self.assertEqual(
            media.file.name,
            "feed/media/deletion-fixture.webp",
        )

    def test_hashtag_counter_and_reverse_visibility(self):
        post = self.make_post()
        survivor = self.make_post()

        tag = Hashtag.objects.create(
            name="deletionfixture"
        )

        post.hashtags.add(tag)
        survivor.hashtags.add(tag)

        tag.refresh_from_db()
        self.assertEqual(tag.usage_count, 2)

        self.delete(post)

        tag.refresh_from_db()

        self.assertEqual(tag.usage_count, 1)

        self.assertFalse(
            tag.posts.filter(pk=post.pk).exists()
        )

        self.assertTrue(
            tag.posts.filter(pk=survivor.pk).exists()
        )

        self.assertFalse(
            self.owner.feedpost_set.filter(
                pk=post.pk
            ).exists()
        )

    def test_deleted_post_endpoints_rejected(self):
        post = self.make_post()

        self.delete(post)

        endpoints = (
            post_detail,
            toggle_post_like,
            add_post_comment,
            toggle_pin_post,
            unlock_feed_post,
            translate_post,
        )

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint.__name__):
                with self.assertRaises(Http404):
                    endpoint(self.request(), post.pk)

    def test_protected_publication_history_preserved(self):
        post = self.make_post()
        now = timezone.now()

        publication = ScheduledPublication.objects.create(
            publication_key="deletion-regression",
            creator=self.owner,
            source_path="test/source.jpg",
            scheduled_for=now,
            status=ScheduledPublication.STATUS_PUBLISHED,
            feed_post=post,
            published_at=now,
        )

        attempt = CreatorPublishingAttempt.objects.create(
            publication=publication,
            token=uuid.uuid4(),
            status=CreatorPublishingAttempt.STATUS_COMPLETED,
            claimed_at=now - timedelta(minutes=5),
            lease_expires_at=now + timedelta(minutes=5),
            media_namespace="deletion-regression",
            completed_at=now,
        )

        lease = LegacyAIPublicationLease.objects.create(
            publication=publication,
        )

        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                publication.delete()

        self.assertEqual(
            self.delete(post).status_code, 302
        )

        publication.refresh_from_db()

        self.assertEqual(
            publication.status,
            ScheduledPublication.STATUS_PUBLISHED,
        )

        self.assertEqual(
            publication.feed_post_id, post.pk
        )

        self.assertIsNotNone(
            publication.feed_post.deleted_at
        )

        self.assertTrue(
            CreatorPublishingAttempt.objects.filter(
                pk=attempt.pk,
                status=CreatorPublishingAttempt.STATUS_COMPLETED,
            ).exists()
        )

        self.assertTrue(
            LegacyAIPublicationLease.objects.filter(
                pk=lease.pk
            ).exists()
        )



class FeedPostDeletionHTTPTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username="httpdeletionowner"
        )
        self.viewer = User.objects.create_user(
            username="httpdeletionviewer"
        )
        self.post = FeedPost.objects.create(
            user=self.owner,
            title="WP015UniqueDeletionMarker",
            content="WP015UniqueDeletionMarker",
            is_public=True,
        )

    def test_owner_http_deletion_and_direct_access(self):
        from django.urls import reverse
        from django.test import Client

        client = Client()
        client.force_login(self.owner)

        detail = reverse(
            "post_detail", args=[self.post.pk]
        )
        deletion = reverse(
            "delete_feed_post", args=[self.post.pk]
        )

        self.assertEqual(
            client.get(detail).status_code, 200
        )

        response = client.post(deletion)

        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            FeedPost.objects.filter(
                pk=self.post.pk
            ).exists()
        )

        client.force_login(self.viewer)

        response = client.get(detail)

        # FANZ middleware may redirect GET 404 responses.
        self.assertIn(response.status_code, (302, 404))

        for name in (
            "toggle_post_like",
            "add_post_comment",
            "unlock_feed_post",
            "toggle_pin_post",
        ):
            with self.subTest(endpoint=name):
                response = client.post(
                    reverse(name, args=[self.post.pk])
                )
                self.assertEqual(response.status_code, 404)

    def test_profile_and_community_exclude_deleted_post(self):
        from django.urls import reverse
        from django.test import Client

        client = Client()
        client.force_login(self.owner)

        profile = reverse(
            "public_profile",
            kwargs={"username": self.owner.username},
        )
        community = reverse("feed_home")

        for url in (profile, community):
            response = client.get(url, follow=True)
            self.assertContains(
                response, "WP015UniqueDeletionMarker"
            )

        client.post(
            reverse(
                "delete_feed_post",
                args=[self.post.pk],
            )
        )

        for user in (self.owner, self.viewer):
            client.force_login(user)

            for url in (profile, community):
                with self.subTest(user=user.username, url=url):
                    response = client.get(url, follow=True)
                    self.assertNotContains(
                        response, "WP015UniqueDeletionMarker"
                    )



from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import TransactionTestCase


class FeedPostDeletionConcurrencyTests(TransactionTestCase):

    def test_concurrent_owner_deletion(self):
        self.assertEqual(connection.vendor, "postgresql")

        owner = User.objects.create_user(
            username="concurrentdeletionowner"
        )

        post = FeedPost.objects.create(
            user=owner,
            title="Concurrent deletion fixture",
            content="Disposable regression fixture",
            is_public=True,
        )

        tag = Hashtag.objects.create(
            name="concurrentdeletion"
        )
        post.hashtags.add(tag)

        barrier = Barrier(2)

        def delete_worker():
            close_old_connections()

            try:
                user = User.objects.get(pk=owner.pk)
                request = RequestFactory().post("/")
                request.user = user

                barrier.wait(timeout=10)

                response = delete_feed_post(
                    request, post.pk
                )

                timestamp = FeedPost.all_objects.get(
                    pk=post.pk
                ).deleted_at

                return response.status_code, timestamp

            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(delete_worker)
                for _ in range(2)
            ]

            results = [
                future.result(timeout=30)
                for future in futures
            ]

        self.assertEqual(
            [result[0] for result in results],
            [302, 302],
        )

        self.assertIsNotNone(results[0][1])
        self.assertEqual(results[0][1], results[1][1])

        self.assertFalse(
            FeedPost.objects.filter(pk=post.pk).exists()
        )

        self.assertEqual(
            FeedPost.all_objects.filter(pk=post.pk).count(),
            1,
        )

        tag.refresh_from_db()
        self.assertEqual(tag.usage_count, 0)

        print("Concurrent deletion workers: 2")
        print("Successful responses: 2")
        print("Historical records retained: 1")
        print("Deletion timestamp consistent: PASS")
        print("Hashtag counter consistency: PASS")



class FeedPostDeletionReplayTests(TestCase):

    def test_deleted_submission_token_remains_consumed(self):
        from unittest.mock import patch

        from auctions.models import FeedPostSubmission
        from auctions.feed_submission_services import (
            FeedSubmissionRejected,
            find_completed_submission,
            publish_once,
        )

        owner = User.objects.create_user(
            username="deletionreplayowner"
        )

        post = FeedPost.objects.create(
            user=owner,
            title="Replay regression fixture",
            content="Replay regression fixture",
            is_public=True,
        )

        token = uuid.uuid4()
        fingerprint = "a" * 64

        submission = FeedPostSubmission.objects.create(
            token=token,
            creator=owner,
            request_fingerprint=fingerprint,
            post=post,
        )

        existing, outcome = find_completed_submission(
            token=token,
            fingerprint=fingerprint,
            creator=owner,
        )

        self.assertEqual(existing.pk, post.pk)

        request = RequestFactory().post("/")
        request.user = owner

        self.assertEqual(
            delete_feed_post(request, post.pk).status_code,
            302,
        )

        with self.assertRaises(FeedSubmissionRejected):
            find_completed_submission(
                token=token,
                fingerprint=fingerprint,
                creator=owner,
            )

        with patch(
            "auctions.alltags_publishing.publish_interactive_post"
        ) as publish:
            with self.assertRaises(FeedSubmissionRejected):
                publish_once(
                    token=token,
                    fingerprint=fingerprint,
                    creator=owner,
                    form=None,
                    alltags=False,
                )

            publish.assert_not_called()

        submission.refresh_from_db()

        self.assertEqual(submission.post_id, post.pk)

        self.assertIsNotNone(
            submission.post.deleted_at
        )

        self.assertEqual(
            FeedPostSubmission.objects.filter(
                token=token
            ).count(),
            1,
        )

        self.assertEqual(
            FeedPost.all_objects.filter(
                user=owner
            ).count(),
            1,
        )

        self.assertFalse(
            FeedPost.objects.filter(
                user=owner
            ).exists()
        )
