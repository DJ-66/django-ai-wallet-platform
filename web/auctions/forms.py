from django import forms
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, UnidentifiedImageError, ImageOps, ImageDraw, ImageFont
from io import BytesIO
import os

from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import FeedPost, UserProfile, DirectMessage

def add_fanz_brand_banner(img, username):
    if not username:
        return img

    img = img.convert("RGBA")

    draw = ImageDraw.Draw(img)
    text = f"❤  Fanz.to/{username}"

    font_size = 75
    
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]

    font = None

    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            
            break
        except OSError:
            continue

    if font is None:
        font = ImageFont.load_default()

    padding_x = font_size // 2
    padding_y = font_size // 3
    margin = font_size // 3
    radius = font_size // 2

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    banner_w = text_w + padding_x * 2
    banner_h = text_h + padding_y * 2

    img_w, img_h = img.size

    x1 = img_w - banner_w - margin
    y1 = img_h - banner_h - margin
    x2 = img_w - margin
    y2 = img_h - margin

    draw.rounded_rectangle(
        [x1, y1, x2, y2],
        radius=radius,
        fill=(0, 0, 0, 160),
        outline=(255, 255, 255, 200),
        width=2,
    )

    text_x = x1 + padding_x
    text_y = y1 + padding_y - bbox[1]

    draw.text(
        (text_x, text_y),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=1,
        stroke_fill=(255, 255, 255, 100),
    )

    return img.convert("RGB")

def add_fanz_auction_footer(img):
    """
    Add simple Fanz.to platform footer below auction images.
    Original image content stays untouched.
    """
    img = img.convert("RGBA")

    width, height = img.size
    footer_height = max(140, int(width * 0.18))

    new_img = Image.new(
        "RGBA",
        (width, height + footer_height),
        (0, 0, 0, 255),
    )

    new_img.paste(img, (0, 0))

    draw = ImageDraw.Draw(new_img)

    brand_text = "Fanz.to"

    font_size = int(footer_height * 0.72)

    try:
        brand_font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except OSError:
        brand_font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    text_x = (width - text_width) // 2
    text_y = height + (footer_height - text_height) // 2 - int(footer_height * 0.06)

    draw.text(
        (text_x, text_y),
        brand_text,
        font=brand_font,
        fill=(255, 255, 255, 255),
    )

    return new_img.convert("RGB")

def process_fanz_image_upload(
    image,
    username=None,
    watermark=False,
    auction_footer=False,
    max_width=1600,
    max_height=2400,
    quality=82,
):
    if not image:
        return image

    max_size = 40 * 1024 * 1024

    if image.size > max_size:
        raise forms.ValidationError(
            _("Image file is too large. Maximum size is 40 MB.")
        )

    try:
        img = Image.open(image)
        original_format = img.format
        img.verify()

        image.seek(0)
        img = Image.open(image)
        img = ImageOps.exif_transpose(img)

    except (UnidentifiedImageError, OSError):
        raise forms.ValidationError(
            _("Upload a valid image file.")
        )

    if original_format not in ["JPEG", "PNG", "WEBP", "AVIF"]:
        raise forms.ValidationError(
            _("Supported image formats are JPG, PNG, WebP, and AVIF.")
        )

    img = img.convert("RGB")
    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

    if auction_footer:
        img = add_fanz_auction_footer(img)
    elif watermark:
        img = add_fanz_brand_banner(img, username)

    output = BytesIO()

    img.save(
        output,
        format="WEBP",
        quality=quality,
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
            username=self.current_username,
            watermark=True,
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
