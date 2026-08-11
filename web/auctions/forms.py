import secrets
from django import forms
from .models import FeedPost, FeedPostMedia
from core.image_utils import process_fanz_image_upload
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError
from .models import (
    DirectMessage,
    Event,
    FeedPost,
    FeedPostTranslation,
    UserProfile,
    UserProfileTranslation,
)

class PlatformAccountForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label=_("Username"),
    )

    display_name = forms.CharField(
        max_length=80,
        required=False,
        label=_("Display name"),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(
            username__iexact=username
        ).exists():
            raise forms.ValidationError(
                _("This username already exists.")
            )

        return username


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

        if not image:
            return image

        username = None

        if self.user and self.user.is_authenticated:
            username = self.user.username

        return process_fanz_image_upload(
            image,
            username=username,
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

class MultipleFeedMediaInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFeedMediaField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MultipleFeedMediaInput(
                attrs={
                    "accept": (
                        "image/*,"
                        "video/mp4,"
                        "audio/mpeg,"
                        "application/pdf,"
                        ".jpg,.jpeg,.png,.webp,.avif,.mp4,.mp3,.pdf"
                    ),
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean

        if isinstance(data, (list, tuple)):
            return [
                single_file_clean(uploaded_file, initial)
                for uploaded_file in data
            ]

        if data:
            return [single_file_clean(data, initial)]

        return []

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class FeedPostForm(forms.ModelForm):
    MEDIA_TYPE_CHOICES = (
        (FeedPostMedia.MEDIA_TYPE_IMAGE, _("Images")),
        (FeedPostMedia.MEDIA_TYPE_VIDEO, _("Videos")),
        (FeedPostMedia.MEDIA_TYPE_AUDIO, _("Audio")),
        (FeedPostMedia.MEDIA_TYPE_PDF, _("PDF (Max 1)")),
    )

    media_type = forms.ChoiceField(
        choices=MEDIA_TYPE_CHOICES,
        widget=forms.RadioSelect(
            attrs={
                "class": "feed-media-type-input",
        }
    ),
        initial=FeedPostMedia.MEDIA_TYPE_IMAGE,
        required=True,
        label=_("Media type"),
)

    images = MultipleFeedMediaField(
        required=False,
        widget=MultipleFileInput(
            attrs={
                "class": "feed-image-input",
        }
    ),
)

    def __init__(self, *args, **kwargs):
        self.current_username = kwargs.pop("current_username", None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = FeedPost
        fields = [
            "title",
            "content",
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


    def clean_images(self):
        uploaded_files = self.cleaned_data.get("images", [])
        is_paid = self.cleaned_data.get("is_paid", False)
        unlock_price = self.cleaned_data.get("unlock_price") or 0

        pdf_files = [
            uploaded_file
            for uploaded_file in uploaded_files
            if (
                getattr(uploaded_file, "content_type", "")
                or ""
            ).lower() == "application/pdf"
        ]

        if len(pdf_files) > 1:
            raise forms.ValidationError(
                (
                    "PDF posts support one document. "
                    "Create a separate post for each additional PDF."
            )
        )

        media_type = self.cleaned_data.get("media_type")

        if media_type == FeedPostMedia.MEDIA_TYPE_PDF:
            if len(uploaded_files) > 1:
                raise forms.ValidationError(
                (
                        "PDF posts support one document. "
                        "Create a separate post for each additional PDF."
                )
            )
        else:
            max_files = (
                8
                if is_paid and unlock_price >= 250
                else 3
            )

            if len(uploaded_files) > max_files:
                raise forms.ValidationError(
                    (
                        f"You may upload a maximum of {max_files} files "
                        "for this post."
                    )
                )

        allowed_image_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/avif",
        }

        allowed_audio_types = {
            "audio/mpeg",
            "audio/mp3",
        }

        max_image_size = 64 * 1024 * 1024
        max_video_size = 250 * 1024 * 1024
        max_audio_size = 50 * 1024 * 1024
        max_pdf_size = 50 * 1024 * 1024
        max_image_pixels = 50_000_000

        cleaned_media = []

        for uploaded_file in uploaded_files:
            content_type = (
                getattr(uploaded_file, "content_type", "")
                or ""
            ).lower()

            file_size = getattr(uploaded_file, "size", 0)

            if content_type in allowed_image_types:
                if file_size > max_image_size:
                    raise forms.ValidationError(
                        "Each image must be 64 MB or smaller."
                    )

                try:
                    uploaded_file.seek(0)

                    with Image.open(uploaded_file) as image:
                        width, height = image.size

                    if width * height > max_image_pixels:
                        raise forms.ValidationError(
                            "Each image must be 50 megapixels or smaller."
                        )

                except UnidentifiedImageError:
                    raise forms.ValidationError(
                        (
                            "One of the uploaded image files is invalid "
                            "or unsupported."
                        )
                    )
                except OSError:
                    raise forms.ValidationError(
                        (
                            "One of the uploaded image files "
                            "could not be read."
                        )
                    )
                finally:
                    uploaded_file.seek(0)

                processed_file = process_fanz_image_upload(
                    uploaded_file,
                    footer_text=f"❤ Fanz.to/{self.current_username}",
                    max_width=1600,
                    max_height=1600,
                    quality=90,
                )

                cleaned_media.append(
                    {
                        "file": processed_file,
                        "media_type": FeedPostMedia.MEDIA_TYPE_IMAGE,
                    }
                )

                continue

            if content_type == "video/mp4":
                if not is_paid:
                    raise forms.ValidationError(
                        (
                            "MP4 video uploads are available only "
                            "for Premium posts."
                        )
                    )

                if file_size > max_video_size:
                    raise forms.ValidationError(
                        "Each MP4 video must be 250 MB or smaller."
                    )

                cleaned_media.append(
                    {
                        "file": uploaded_file,
                        "media_type": FeedPostMedia.MEDIA_TYPE_VIDEO,
                    }
                )

                continue

            if content_type in allowed_audio_types:
                if not is_paid:
                    raise forms.ValidationError(
                        (
                            "MP3 audio uploads are available only "
                            "for Premium posts."
                        )
                    )

                if file_size > max_audio_size:
                    raise forms.ValidationError(
                        "Each MP3 audio file must be 50 MB or smaller."
                    )

                cleaned_media.append(
                    {
                        "file": uploaded_file,
                        "media_type": FeedPostMedia.MEDIA_TYPE_AUDIO,
                    }
                )

                continue

            if content_type == "application/pdf":
                if not is_paid:
                    raise forms.ValidationError(
                        (
                            "PDF uploads are available only "
                            "for Premium posts."
                        )
                    )

                if file_size > max_pdf_size:
                    raise forms.ValidationError(
                        "Each PDF must be 50 MB or smaller."
                    )

                cleaned_media.append(
                    {
                        "file": uploaded_file,
                        "media_type": FeedPostMedia.MEDIA_TYPE_PDF,
                    }
                )

                continue

            raise forms.ValidationError(
                (
                    f"Unsupported file type: {uploaded_file.name}. "
                    "Upload a JPEG, PNG, WebP, AVIF, MP4, MP3, or PDF."
                )
            )

        return cleaned_media

class FeedPostTranslationForm(forms.ModelForm):
    class Meta:
        model = FeedPostTranslation
        fields = [
            "title",
            "content",
        ]

        labels = {
            "title": _("Title"),
            "content": _("Content"),
        }

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": _("Localized post title..."),
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": _("Localized post content..."),
                }
            ),
        }

class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "email", "password"]
    
    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()

        reserved_usernames = {
            "admin",
            "administrator",
            "support",
            "security",
            "official",
            "system",
            "moderator",
            "billing",
            "auctions",
            "discover",
            "help",
            "staff",
            "fanzofficial",
            "bitcoin",
            "dogecoin",
            "monero",
            "medititation",
            "ebook",
            "author",
            "coffee",
            "dating",
            "beachyoga",
            "beach",
            "Encarnacion",
            "python",
            "blockchain",
            "memecoin",
            "music",
            "audio",
            "t-shirt",
            "tshirt",
            "advertise",
            "influencer",
            "digitalnomad",
            "horror",
            "nudes",
            "pizza",
            "freelance",
            "gtwilson",
            "djjordan",
            "watchparty",
        }

        normalized_username = username.lower()

        # Reserve every 1–4 character handle for FANZ/platform use.
        if len(username) <= 4:
            raise forms.ValidationError(
                _(
                    "Usernames with 4 characters or fewer are reserved "
                    "for FANZ platform accounts."
                )
            )

        # Reserve important longer platform/system handles.
        if normalized_username in reserved_usernames:
            raise forms.ValidationError(
                _("This username is reserved for FANZ platform use.")
            )

        # Prevent case variations such as News / NEWS / news.
        if User.objects.filter(
            username__iexact=username
        ).exists():
            raise forms.ValidationError(
                _("This username is already taken.")
            )

        return username

    
    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("An account with this email already exists.")
            )

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

class UserProfileTranslationForm(forms.ModelForm):
    class Meta:
        model = UserProfileTranslation
        fields = [
            "bio",
            "bank_payment_notes",
        ]

        labels = {
            "bio": _("Bio"),
            "bank_payment_notes": _("Payment instructions"),
        }

        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "rows": 6,
                }
            ),
            "bank_payment_notes": forms.Textarea(
                attrs={
                    "rows": 6,
                }
            ),
        }


    def clean_avatar(self):
        image = self.cleaned_data.get("avatar")

        if not image:
            return image

        user_id = getattr(
            getattr(self.instance, "user", None),
            "id",
            "user",
        )

        token = secrets.token_hex(3)

        return process_fanz_image_upload(
            image,
            watermark=False,
            max_width=600,
            max_height=600,
            quality=86,
            output_name=f"avatar-{user_id}-{token}",
        )

    def clean_banner(self):
        image = self.cleaned_data.get("banner")

        if not image:
            return image

        user_id = getattr(
            getattr(self.instance, "user", None),
            "id",
            "user",
        )

        token = secrets.token_hex(3)

        return process_fanz_image_upload(
            image,
            watermark=False,
            max_width=1800,
            max_height=700,
            quality=86,
            output_name=f"banner-{user_id}-{token}",
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
