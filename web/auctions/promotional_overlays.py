"""Reusable, non-destructive FANZ promotional image overlays."""

from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

from .qr_utils import make_branded_referral_qr


FONT_REGULAR = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)
FONT_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)


def _font(size, bold=False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(path, max(10, int(size)))


def _wrap(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()

        if draw.textbbox(
            (0, 0), candidate, font=font
        )[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def _fit_text(draw, text, max_width, max_height, size):
    for font_size in range(size, 9, -1):
        font = _font(font_size, bold=True)
        lines = _wrap(draw, text, font, max_width)

        line_height = int(font_size * 1.35)

        if (
            len(lines) * line_height <= max_height
            and all(
                draw.textbbox(
                    (0, 0), line, font=font
                )[2] <= max_width
                for line in lines
            )
        ):
            return font, lines, line_height

    raise ValueError(
        "Promotional headline does not fit the image."
    )


def _normalize_canvas(image):
    """
    Normalize output dimensions without distorting the source.

    Portrait: 1000x1500
    Landscape: 1600x900
    """
    width, height = image.size

    if width == height:
        raise ValueError(
            "Square promotional images are unsupported."
        )

    portrait = height > width

    target = (
        (1000, 1500)
        if portrait
        else (1600, 900)
    )

    background = ImageOps.fit(
        image,
        target,
        method=Image.Resampling.LANCZOS,
    )

    background = background.filter(
        ImageFilter.GaussianBlur(radius=35)
    )

    background = Image.blend(
        background,
        Image.new("RGB", target, (18, 14, 35)),
        0.35,
    )

    foreground = ImageOps.contain(
        image,
        target,
        method=Image.Resampling.LANCZOS,
    )

    x = (target[0] - foreground.width) // 2
    y = (target[1] - foreground.height) // 2

    background.paste(foreground, (x, y))

    return background


def _draw_glowing_text(
    image,
    position,
    text,
    *,
    font,
    fill,
    glow_color,
    glow_radius,
):
    """Draw softly glowing text without changing the background."""

    glow_layer = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0),
    )

    glow_draw = ImageDraw.Draw(glow_layer)

    glow_draw.text(
        position,
        text,
        font=font,
        fill=(*glow_color, 210),
        stroke_width=max(2, int(font.size * 0.09)),
        stroke_fill=(*glow_color, 210),
    )

    glow_layer = glow_layer.filter(
        ImageFilter.GaussianBlur(radius=glow_radius)
    )

    image.alpha_composite(glow_layer)

    draw = ImageDraw.Draw(image)

    draw.text(
        position,
        text,
        font=font,
        fill=fill,
        stroke_width=max(1, int(font.size * 0.025)),
        stroke_fill=(20, 15, 35, 220),
    )


def _validate_referral_url(url):
    """Allow only the canonical FANZ referral signup endpoint."""
    if not isinstance(url, str):
        raise ValueError("Invalid referral URL.")

    parsed = urlsplit(url)

    if (
        parsed.scheme != "https"
        or parsed.netloc != "fanz.to"
        or parsed.path != "/auctions/signup/"
        or parsed.fragment
    ):
        raise ValueError("Invalid FANZ referral URL.")

    try:
        params = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except ValueError as exc:
        raise ValueError("Invalid referral parameters.") from exc

    if (
        len(params) != 1
        or params[0][0] != "ref"
        or not params[0][1]
        or not params[0][1].isascii()
        or not params[0][1].isalnum()
        or len(params[0][1]) > 12
    ):
        raise ValueError("Invalid referral code.")

    return url


def render_promotional_overlay(
    image_file,
    *,
    headline,
    cta,
    language,
    qr_url=None,
):
    """
    Return a new WebP ContentFile.

    The original image is never modified.
    Portrait: text at top.
    Landscape: text at left.
    """

    if language not in ("en", "es", "pt"):
        raise ValueError("Unsupported language.")

    if not headline.strip() or not cta.strip():
        raise ValueError("Headline and CTA are required.")

    with Image.open(image_file) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")

    image = _normalize_canvas(image)

    width, height = image.size
    portrait = height > width

    # Work at the normalized resolution.
    overlay = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0),
    )

    pixels = overlay.load()

    if portrait:
        # Darken the upper 45%.
        extent = max(1, int(height * 0.45))

        for y in range(extent):
            strength = int(170 * (1 - y / extent))

            for x in range(width):
                pixels[x, y] = (12, 10, 30, strength)

        margin = max(12, int(width * 0.07))
        text_x = margin
        text_y = max(16, int(height * 0.07))
        text_width = width - margin * 2
        text_height = int(height * 0.23)

    else:
        # Darken the left 55%.
        extent = max(1, int(width * 0.55))

        for x in range(extent):
            strength = int(175 * (1 - x / extent))

            for y in range(height):
                pixels[x, y] = (12, 10, 30, strength)

        margin = max(12, int(width * 0.05))
        text_x = margin
        text_y = int(height * 0.24)
        text_width = int(width * 0.43)
        text_height = int(height * 0.30)

    image = Image.alpha_composite(
        image.convert("RGBA"),
        overlay,
    )

    draw = ImageDraw.Draw(image)

    headline_font, lines, line_height = _fit_text(
        draw,
        headline,
        text_width,
        text_height,
        max(16, int(min(width, height) * 0.0845)),
    )

    for index, line in enumerate(lines):
        _draw_glowing_text(
            image,
            (
                text_x,
                text_y + index * line_height,
            ),
            line,
            font=headline_font,
            fill=(255, 255, 255, 255),
            glow_color=(155, 90, 255),
            glow_radius=max(5, int(headline_font.size * 0.20)),
        )

    cta_y = (
        text_y
        + len(lines) * line_height
        + max(10, int(height * 0.025))
    )

    cta_font = _font(
        max(12, int(min(width, height) * 0.0455)),
        bold=True,
    )

    if draw.textbbox(
        (0, 0), cta, font=cta_font
    )[2] > text_width:
        raise ValueError("Promotional CTA is too long.")

    _draw_glowing_text(
        image,
        (text_x, cta_y),
        cta,
        font=cta_font,
        fill=(255, 225, 110, 255),
        glow_color=(255, 175, 35),
        glow_radius=max(4, int(cta_font.size * 0.18)),
    )

    if qr_url:
        qr_url = _validate_referral_url(qr_url)

        qr = make_branded_referral_qr(
            qr_url
        ).convert("RGBA")

        # Keep the QR large enough for scanning.
        qr_size = 286 if portrait else 260

        qr = qr.resize(
            (qr_size, qr_size),
            Image.Resampling.NEAREST,
        )

        labels = {
            "en": "SCAN TO JOIN FREE",
            "es": "ESCANEA Y ÚNETE GRATIS",
            "pt": "ESCANEIE E ENTRE GRÁTIS",
        }

        label = labels[language]
        padding = 16
        label_height = 42

        backing_width = qr_size + 2 * padding
        backing_height = (
            qr_size + 2 * padding + label_height
        )

        backing = Image.new(
            "RGBA",
            (backing_width, backing_height),
            (255, 255, 255, 255),
        )

        label_draw = ImageDraw.Draw(backing)

        for size in range(20, 11, -1):
            label_font = _font(size, bold=True)
            bbox = label_draw.textbbox(
                (0, 0),
                label,
                font=label_font,
            )

            label_width = bbox[2] - bbox[0]

            if label_width <= backing_width - 12:
                break
        else:
            raise ValueError(
                "QR instruction does not fit."
            )

        label_x = (backing_width - label_width) // 2
        label_y = max(
            2,
            (label_height - (bbox[3] - bbox[1])) // 2
            - bbox[1],
        )

        label_draw.text(
            (label_x, label_y),
            label,
            font=label_font,
            fill=(55, 30, 110, 255),
        )

        backing.alpha_composite(
            qr,
            (padding, padding + label_height),
        )

        x = max(24, int(width * 0.04))
        y = (
            height
            - backing_height
            - max(30, int(height * 0.05))
        )

        image.alpha_composite(
            backing,
            (x, y),
        )

    output = BytesIO()

    image.convert("RGB").save(
        output,
        format="WEBP",
        quality=90,
        method=6,
    )

    return ContentFile(
        output.getvalue(),
        name=f"fanz-promo-{language}.webp",
    )
