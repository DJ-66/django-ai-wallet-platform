import os
from io import BytesIO

from django import forms
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import gettext_lazy as _

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageOps,
    UnidentifiedImageError,
)


def add_fanz_brand_banner(img, username):
    if not username:
        return img

    img = img.convert("RGBA")

    draw = ImageDraw.Draw(img)
    text = f"❤  Fanz.to/{username}"

    img_w, img_h = img.size

    font_size = max(
        18,
        min(75, int(min(img_w, img_h) * 0.075)),
    )

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

def add_fanz_platform_footer(
    img,
    text="Fanz.to",
):
    """
    Add simple Fanz.to platform footer below platform images.
    Original image content stays untouched.
    """
    img = img.convert("RGBA")

    width, height = img.size
    footer_height = max(60, int(width * 0.075))

    new_img = Image.new(
        "RGBA",
        (width, height + footer_height),
        (0, 0, 0, 255),
    )

    new_img.paste(img, (0, 0))

    draw = ImageDraw.Draw(new_img)

    brand_text = text

    font_size = int(footer_height * 0.60)

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
    platform_footer=False,
    footer_text=None,
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

    if footer_text:
        img = add_fanz_platform_footer(
            img,
            text=footer_text,
        )
    elif platform_footer:
        img = add_fanz_platform_footer(img)
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

