from django import forms

from .models import Auction


class AuctionAdminForm(forms.ModelForm):
    starting_price = forms.DecimalField(
        min_value=1,
        max_digits=10,
        decimal_places=2,
        help_text="Enter a whole-number starting price.",
        widget=forms.NumberInput(
            attrs={
                "step": "1",
                "min": "1",
            }
        ),
    )

    bid_increment = forms.DecimalField(
        min_value=1,
        max_digits=10,
        decimal_places=2,
        help_text="Enter a whole-number credit increment.",
        widget=forms.NumberInput(
            attrs={
                "step": "1",
                "min": "1",
            }
        ),
    )

    class Meta:
        model = Auction
        exclude = (
            "image",
            "image_2",
            "video",
            "current_price",
        )

    def _validate_whole_number(self, field_name):
        value = self.cleaned_data.get(field_name)

        if value is not None and value != value.to_integral_value():
            raise forms.ValidationError(
                "Enter a whole number without cents."
            )

        return value

    def clean_starting_price(self):
        return self._validate_whole_number("starting_price")

    def clean_bid_increment(self):
        return self._validate_whole_number("bid_increment")


class MultipleAuctionImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleAuctionImageField(forms.FileField):
    def clean(self, data, initial=None):
        single_file_clean = super().clean

        if isinstance(data, (list, tuple)):
            return [
                single_file_clean(uploaded_file, initial)
                for uploaded_file in data
            ]

        if data:
            return [
                single_file_clean(data, initial)
            ]

        return single_file_clean(data, initial)


class AuctionStudioImageUploadForm(forms.Form):
    images = MultipleAuctionImageField(
        required=True,
        widget=MultipleAuctionImageInput(
            attrs={
                "accept": (
                    "image/jpeg,"
                    "image/png,"
                    "image/webp,"
                    "image/avif,"
                    ".jpg,.jpeg,.png,.webp,.avif"
                ),
            }
        ),
        label="Upload images",
        help_text="Choose up to 8 auction images.",
    )

    def clean_images(self):
        files = self.cleaned_data["images"]

        if len(files) > 8:
            raise forms.ValidationError(
                "You may select a maximum of 8 images."
            )

        return files


class AuctionStudioVideoUploadForm(forms.Form):
    video = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "video/mp4,.mp4",
            }
        ),
        label="Upload video",
        help_text="Choose one MP4 auction video.",
    )

    def clean_video(self):
        uploaded_file = self.cleaned_data["video"]

        filename = getattr(
            uploaded_file,
            "name",
            "",
        ).lower()

        content_type = (
            getattr(
                uploaded_file,
                "content_type",
                "",
            )
            or ""
        ).lower()

        if not filename.endswith(".mp4"):
            raise forms.ValidationError(
                "Auction video must be an MP4 file."
            )

        if content_type and content_type not in (
            "video/mp4",
            "application/mp4",
            "application/octet-stream",
        ):
            raise forms.ValidationError(
                "The uploaded file is not recognized as an MP4 video."
            )

        max_size = 50 * 1024 * 1024

        if uploaded_file.size > max_size:
            raise forms.ValidationError(
                "Auction video must be 50 MB or smaller."
            )

        return uploaded_file
