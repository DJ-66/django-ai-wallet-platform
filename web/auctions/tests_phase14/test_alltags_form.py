from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from auctions.forms import FeedPostForm


class AllTagsFormTests(SimpleTestCase):

    def make_image(self):
        buffer = BytesIO()
        Image.new("RGB", (32, 32)).save(
            buffer, format="PNG"
        )
        return SimpleUploadedFile(
            "test.png",
            buffer.getvalue(),
            content_type="image/png",
        )

    def make_form(
        self,
        *,
        alltags=True,
        public=True,
        paid=False,
        price=0,
        image=True,
    ):
        return FeedPostForm(
            data={
                "title": "Test post",
                "content": "Public image test",
                "media_type": "image",
                "is_public": public,
                "is_paid": paid,
                "unlock_price": price,
                "alltags_requested": alltags,
            },
            files={
                "images": [self.make_image()] if image else [],
            },
            current_username="TestCreator",
        )

    def test_valid_public_image_promotion(self):
        self.assertTrue(
            self.make_form().is_valid()
        )

    def test_private_post_valid_with_optional_promotion(self):
        self.assertTrue(
            self.make_form(public=False).is_valid()
        )

    def test_paid_post_valid_with_optional_promotion(self):
        self.assertTrue(
            self.make_form(paid=True).is_valid()
        )

    def test_unlock_price_follows_existing_validation(self):
        self.assertTrue(
            self.make_form(price=5).is_valid()
        )

    def test_image_free_post_valid_with_optional_promotion(self):
        self.assertTrue(
            self.make_form(image=False).is_valid()
        )

    def test_ordinary_public_post_unaffected(self):
        self.assertTrue(
            self.make_form(alltags=False).is_valid()
        )
