"""FANZ optional WebP output-size regression tests."""

from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from core.image_utils import process_fanz_image_upload


def make_image(size=(1200, 800), mode="RGB"):
    output = BytesIO()
    color = (80, 120, 180) if mode == "RGB" else (80, 120, 180, 100)
    Image.new(mode, size, color).save(output, format="PNG")
    return SimpleUploadedFile(
        "test.png",
        output.getvalue(),
        content_type="image/png",
    )


class FanzImageSizeOptimizerTests(SimpleTestCase):
    def test_default_webp_conversion(self):
        result = process_fanz_image_upload(make_image())
        self.assertEqual(result.content_type, "image/webp")
        with Image.open(result) as image:
            self.assertEqual(image.format, "WEBP")

    def test_output_respects_byte_limit(self):
        result = process_fanz_image_upload(
            make_image(),
            max_output_bytes=100_000,
        )
        self.assertLessEqual(result.size, 100_000)

    def test_aspect_ratio_preserved(self):
        result = process_fanz_image_upload(
            make_image(size=(1200, 600)),
            max_output_bytes=100_000,
        )
        with Image.open(result) as image:
            self.assertAlmostEqual(
                image.width / image.height,
                2.0,
                delta=0.02,
            )

    def test_invalid_size_limit_rejected(self):
        with self.assertRaises(ValueError):
            process_fanz_image_upload(
                make_image(),
                max_output_bytes=0,
            )

    def test_impossible_size_limit_rejected(self):
        with self.assertRaises(ValidationError):
            process_fanz_image_upload(
                make_image(),
                max_output_bytes=1,
            )

    def test_original_upload_remains_available(self):
        upload = make_image()
        original = upload.read()
        upload.seek(0)

        process_fanz_image_upload(
            upload,
            max_output_bytes=100_000,
        )

        upload.seek(0)
        self.assertEqual(upload.read(), original)

    def test_transparent_png_preserves_alpha(self):
        result = process_fanz_image_upload(make_image(mode="RGBA"))
        with Image.open(result) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.mode, "RGBA")
            self.assertLess(image.getpixel((10, 10))[3], 255)

    def test_palette_transparency_preserved(self):
        output = BytesIO()
        image = Image.new("P", (100, 100), color=0)
        image.putpalette([255, 0, 0] + [0, 0, 0] * 255)
        image.info["transparency"] = 0
        image.save(output, format="PNG")

        upload = SimpleUploadedFile(
            "palette.png",
            output.getvalue(),
            content_type="image/png",
        )

        result = process_fanz_image_upload(upload)

        with Image.open(result) as converted:
            self.assertEqual(converted.mode, "RGBA")
            self.assertEqual(converted.getpixel((10, 10))[3], 0)

    def test_opaque_photo_remains_rgb(self):
        result = process_fanz_image_upload(make_image(mode="RGB"))
        with Image.open(result) as image:
            self.assertEqual(image.mode, "RGB")

    def test_transparent_webp_respects_size_limit(self):
        result = process_fanz_image_upload(
            make_image(mode="RGBA"),
            max_output_bytes=100_000,
        )
        self.assertLessEqual(result.size, 100_000)
        with Image.open(result) as image:
            self.assertEqual(image.mode, "RGBA")

    def test_transparent_banner_preserves_background(self):
        result = process_fanz_image_upload(
            make_image(size=(800, 800), mode="RGBA"),
            username="TestCreator",
            watermark=True,
        )

        with Image.open(result) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.mode, "RGBA")
            self.assertLess(image.getpixel((10, 10))[3], 255)

    def test_transparent_footer_preserves_background(self):
        result = process_fanz_image_upload(
            make_image(size=(800, 800), mode="RGBA"),
            platform_footer=True,
        )

        with Image.open(result) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.mode, "RGBA")
            self.assertLess(image.getpixel((10, 10))[3], 255)
            self.assertEqual(image.getpixel((10, 850))[3], 255)

    def test_opaque_branded_photo_valid_webp(self):
        result = process_fanz_image_upload(
            make_image(mode="RGB"),
            username="TestCreator",
            watermark=True,
        )

        with Image.open(result) as image:
            self.assertEqual(image.format, "WEBP")
            image.verify()

    def test_branded_webp_respects_size_limit(self):
        result = process_fanz_image_upload(
            make_image(mode="RGBA"),
            username="TestCreator",
            watermark=True,
            max_output_bytes=100_000,
        )

        self.assertLessEqual(result.size, 100_000)

        with Image.open(result) as image:
            self.assertEqual(image.format, "WEBP")
