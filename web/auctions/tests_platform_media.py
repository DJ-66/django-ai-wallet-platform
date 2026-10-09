from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.datastructures import MultiValueDict

from PIL import Image

from auctions.models import PlatformMediaAsset
from auctions.platform_media_forms import PlatformMediaUploadForm
from auctions.platform_media_services import save_platform_media


User = get_user_model()


def make_image(name, color):
    output = BytesIO()

    Image.new(
        "RGB",
        (1280, 720),
        color,
    ).save(output, format="JPEG")

    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type="image/jpeg",
    )


class PlatformMediaStorageTests(TestCase):

    def setUp(self):
        self.temp_media = TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)

        media_override = override_settings(
            MEDIA_ROOT=self.temp_media.name
        )
        media_override.enable()
        self.addCleanup(media_override.disable)

        self.account = User.objects.create_user(
            username="SunsetCam"
        )

    def prepare(self, uploads):
        form = PlatformMediaUploadForm(
            data={},
            files=MultiValueDict({
                "images": uploads,
            }),
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

        return form.cleaned_data["images"]

    def test_two_images_saved_as_webp(self):
        items = self.prepare([
            make_image("one.jpg", (200, 100, 80)),
            make_image("two.jpg", (80, 100, 200)),
        ])

        created, duplicates = save_platform_media(
            self.account,
            items,
        )

        self.assertEqual(created, 2)
        self.assertEqual(duplicates, 0)

        assets = PlatformMediaAsset.objects.filter(
            account=self.account
        )

        self.assertEqual(assets.count(), 2)

        for asset in assets:
            self.assertTrue(
                asset.image.name.endswith(".webp")
            )
            self.assertTrue(
                asset.image.storage.exists(
                    asset.image.name
                )
            )

    def test_duplicate_image_skipped(self):
        first = self.prepare([
            make_image("same.jpg", (200, 100, 80)),
        ])

        self.assertEqual(
            save_platform_media(self.account, first),
            (1, 0),
        )

        second = self.prepare([
            make_image("same-again.jpg", (200, 100, 80)),
        ])

        self.assertEqual(
            save_platform_media(self.account, second),
            (0, 1),
        )

        self.assertEqual(
            PlatformMediaAsset.objects.filter(
                account=self.account
            ).count(),
            1,
        )

    def test_different_accounts_can_use_same_image(self):
        other = User.objects.create_user(
            username="Coffee"
        )

        first = self.prepare([
            make_image("same.jpg", (200, 100, 80)),
        ])

        second = self.prepare([
            make_image("same.jpg", (200, 100, 80)),
        ])

        self.assertEqual(
            save_platform_media(self.account, first),
            (1, 0),
        )

        self.assertEqual(
            save_platform_media(other, second),
            (1, 0),
        )


from django.urls import reverse
from auctions.models import FeedPost, UserProfile


class PlatformMediaBrowserTests(PlatformMediaStorageTests):

    def setUp(self):
        super().setUp()

        self.admin = User.objects.create_user(
            username="dj",
            password="test-password",
        )

        self.other = User.objects.create_user(
            username="ordinary_user",
            password="test-password",
        )

        profile, _ = UserProfile.objects.get_or_create(
            user=self.account,
        )
        profile.is_platform_account = True
        profile.save(update_fields=["is_platform_account"])

        self.url = reverse(
            "platform_account_media",
            args=[self.account.pk],
        )

    def test_dj_can_open_media_manager(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Platform Media Manager")

    def test_ordinary_user_cannot_upload(self):
        self.client.force_login(self.other)

        response = self.client.post(
            self.url,
            {
                "images": [
                    make_image("blocked.jpg", (100, 150, 200)),
                ],
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            PlatformMediaAsset.objects.count(),
            0,
        )

    def test_dj_upload_creates_media_not_feed_post(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            self.url,
            {
                "images": [
                    make_image("first.jpg", (200, 100, 80)),
                    make_image("second.jpg", (80, 100, 200)),
                ],
            },
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            PlatformMediaAsset.objects.filter(
                account=self.account
            ).count(),
            2,
        )

        self.assertEqual(
            FeedPost.objects.count(),
            0,
        )

    def test_duplicate_browser_upload_skipped(self):
        self.client.force_login(self.admin)

        for _ in range(2):
            response = self.client.post(
                self.url,
                {
                    "images": [
                        make_image("same.jpg", (200, 100, 80)),
                    ],
                },
            )
            self.assertEqual(response.status_code, 302)

        self.assertEqual(
            PlatformMediaAsset.objects.filter(
                account=self.account
            ).count(),
            1,
        )

    def test_non_platform_account_rejected(self):
        self.client.force_login(self.admin)

        url = reverse(
            "platform_account_media",
            args=[self.other.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class PlatformMediaToggleTests(PlatformMediaBrowserTests):

    def make_asset(self):
        items = self.prepare([
            make_image("toggle.jpg", (120, 180, 220)),
        ])
        save_platform_media(self.account, items)

        return PlatformMediaAsset.objects.get(
            account=self.account
        )

    def test_dj_can_deactivate_and_reactivate(self):
        asset = self.make_asset()
        self.client.force_login(self.admin)

        url = reverse(
            "platform_media_toggle",
            args=[self.account.pk, asset.pk],
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        asset.refresh_from_db()
        self.assertFalse(asset.is_active)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        asset.refresh_from_db()
        self.assertTrue(asset.is_active)

    def test_ordinary_user_cannot_toggle(self):
        asset = self.make_asset()
        self.client.force_login(self.other)

        url = reverse(
            "platform_media_toggle",
            args=[self.account.pk, asset.pk],
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

        asset.refresh_from_db()
        self.assertTrue(asset.is_active)

    def test_get_cannot_toggle(self):
        asset = self.make_asset()
        self.client.force_login(self.admin)

        url = reverse(
            "platform_media_toggle",
            args=[self.account.pk, asset.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)

        asset.refresh_from_db()
        self.assertTrue(asset.is_active)
