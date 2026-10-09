import hashlib

from django import forms
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

from core.image_utils import process_fanz_image_upload
from auctions.forms import MultipleFileInput


class PlatformMediaFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            if self.required:
                raise forms.ValidationError(
                    _("Select at least one image.")
                )
            return []

        if not isinstance(data, (list, tuple)):
            data = [data]

        if len(data) > 30:
            raise forms.ValidationError(
                _("Upload a maximum of 30 images at once.")
            )

        return [
            super(PlatformMediaFileField, self).clean(
                item,
                initial,
            )
            for item in data
        ]


class PlatformMediaUploadForm(forms.Form):
    images = PlatformMediaFileField(
        required=True,
        widget=MultipleFileInput(
            attrs={
                "accept": (
                    "image/jpeg,image/png,"
                    "image/webp,image/avif"
                ),
            }
        ),
        label=_("Upload images"),
    )

    def clean_images(self):
        uploads = self.cleaned_data["images"]
        processed = []

        for image in uploads:
            if image.size > 10 * 1024 * 1024:
                raise forms.ValidationError(
                    _("Each image must be 10 MB or smaller.")
                )

            try:
                image.seek(0)

                with Image.open(image) as img:
                    width, height = img.size
                    image_format = img.format
                    img.verify()

                if width * height > 25_000_000:
                    raise forms.ValidationError(
                        _("Each image must be 25 megapixels or smaller.")
                    )

                if image_format not in (
                    "JPEG", "PNG", "WEBP", "AVIF"
                ):
                    raise forms.ValidationError(
                        _("Unsupported image format.")
                    )

                image.seek(0)

                digest = hashlib.sha256()

                for chunk in image.chunks():
                    digest.update(chunk)

                original_sha256 = digest.hexdigest()
                image.seek(0)

                processed_file = process_fanz_image_upload(
                    image,
                    watermark=False,
                    platform_footer=False,
                    max_width=1600,
                    max_height=1600,
                    quality=90,
                )

                processed.append({
                    "file": processed_file,
                    "sha256": original_sha256,
                })

            except (
                UnidentifiedImageError,
                OSError,
                ValueError,
            ):
                raise forms.ValidationError(
                    _("One of the images is invalid.")
                )
            finally:
                image.seek(0)

        return processed
