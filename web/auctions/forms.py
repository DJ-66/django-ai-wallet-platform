from django import forms
from core.image_utils import process_fanz_image_upload
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError
from .models import (
    DirectMessage,
    Event,
    FeedPost,
    UserProfile,
)


class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        business_field = self.fields.get("business")

        if business_field is None:
            return

        if self.user and self.user.is_authenticated:
            business_field.queryset = business_field.queryset.filter(
                owner=self.user,
                is_active=True,
            )
        else:
            business_field.queryset = business_field.queryset.none()

    class Meta:
        model = Event
        fields = [
            "business",
            "event_type",
            "title",
            "description",
            "start_at",
            "end_at",
            "location",
            "image",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": _("Event title..."),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": _("Describe the event..."),
                }
            ),
            "start_at": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                }
            ),
            "end_at": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "placeholder": _("Event location..."),
                }
            ),

            "image": forms.ClearableFileInput(
                attrs={
                    "accept": "image/jpeg,image/png,image/webp",
                }
            ),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")

        return process_fanz_image_upload(
            image,
            username=self.current_username,
            watermark=False,
        )

    def clean(self):
        cleaned_data = super().clean()

        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")

        if start_at and end_at and end_at < start_at:
            self.add_error(
                "end_at",
                _("End time cannot be earlier than start time."),
            )

        return cleaned_data


class FeedPostForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.current_username = kwargs.pop("current_username", None)
        super().__init__(*args, **kwargs)

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

        return process_fanz_image_upload(
            image,
            footer_text=f"❤ Fanz.to/{self.current_username}",
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
            "whatsapp",
            "featured_link_1_label",
            "featured_link_1_url",
            "featured_link_2_label",
            "featured_link_2_url",
            "featured_link_3_label",
            "featured_link_3_url",

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
            "whatsapp": "WhatsApp",
            "featured_link_1_label": _("Featured link 1 label"),
            "featured_link_1_url": _("Featured link 1 URL"),
            "featured_link_2_label": _("Featured link 2 label"),
            "featured_link_2_url": _("Featured link 2 URL"),
            "featured_link_3_label": _("Featured link 3 label"),
            "featured_link_3_url": _("Featured link 3 URL"),

}

    def clean_avatar(self):
        image = self.cleaned_data.get("avatar")

        return process_fanz_image_upload(
            image,
            watermark=False,
            max_width=600,
            max_height=600,
            quality=86,
        )

    def clean_banner(self):
        image = self.cleaned_data.get("banner")

        return process_fanz_image_upload(
            image,
            watermark=False,
            max_width=1800,
            max_height=700,
            quality=86,
        )

    def clean_bank_qr_image(self):
        image = self.cleaned_data.get("bank_qr_image")

        if not image:
            return image

        max_size = 10 * 1024 * 1024

        if image.size > max_size:
            raise forms.ValidationError(
                _("QR image file is too large. Maximum size is 10 MB.")
            )

        try:
            img = Image.open(image)
            original_format = img.format
            img.verify()
            image.seek(0)

        except (UnidentifiedImageError, OSError):
            raise forms.ValidationError(
                _("Upload a valid QR image file.")
            )

        if original_format not in ["JPEG", "PNG", "WEBP"]:
            raise forms.ValidationError(
                _("Supported QR image formats are JPG, PNG, and WebP.")
            )

        return image

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
