from django import forms
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, UnidentifiedImageError, ImageOps
from io import BytesIO
import os

from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import FeedPost, UserProfile, DirectMessage

class FeedPostForm(forms.ModelForm):
    class Meta:
        model = FeedPost
        fields = [
            "title",
            "content",
            "image",
            "is_public",
            "is_paid",
            "unlock_price",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": _("Post title..."),
                "class": "feed-post-title-input",
            }),

            "content": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": _("What's happening?"),
            }),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")

        if not image:
            return image

        max_size = 40 * 1024 * 1024

        if image.size > max_size:
            raise forms.ValidationError(
                _("Image file is too large. Maximum size is 40 MB.")
            )

        try:
            img = Image.open(image)
            img.verify()

            image.seek(0)
            img = Image.open(image)
            img = ImageOps.exif_transpose(img)


        except (UnidentifiedImageError, OSError):
            raise forms.ValidationError(
                _("Upload a valid image file.")
            )

        if img.format not in ["JPEG", "PNG", "WEBP", "AVIF"]:
            raise forms.ValidationError(
                _("Supported image formats are JPG, PNG, WebP, and AVIF.")
            )

        img = img.convert("RGB")

        max_width = 1600
        max_height = 2400

        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        output = BytesIO()
        img.save(
            output,
            format="WEBP",
            quality=82,
            method=6,
            optimize=True,
        )
        output.seek(0)

        original_name = os.path.splitext(image.name)[0]
        new_name = f"{original_name}.webp"

        return InMemoryUploadedFile(
            output,
            "ImageField",
            new_name,
            "image/webp",
            output.getbuffer().nbytes,
            None,
        )

class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")

        return email


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "display_name",
            "bio",
            "avatar",
            "banner",
            "bank_qr_image",
            "bank_payment_notes",
            "location",
            "website",
            "youtube",
            "instagram",
            "x_url",
            "tiktok",
            "telegram",
        ]


        labels = {
            "display_name": _("Display name"),
            "bio": _("Bio"),
            "avatar": _("Avatar"),
            "banner": _("Banner"),
            "bank_qr_image": _("Payment QR Code"),
            "bank_payment_notes": _("Payment instructions"),
            "location": _("Location"),
            "website": _("Website"),

            # brand names stay as-is
            "youtube": "YouTube",
            "instagram": "Instagram",
            "x_url": "X.com",
            "tiktok": "TikTok",
            "telegram": "Telegram",
}

class DirectMessageForm(forms.ModelForm):
    class Meta:
        model = DirectMessage
        fields = ["body"]

        widgets = {
            "body": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": _("Write a message..."),
                "class": "dm-message-input",
                "autocomplete": "on",
                "autocapitalize": "sentences",
                "spellcheck": "true",
            }),
        }
