from pathlib import Path

import qrcode
from django.conf import settings
from PIL import Image, ImageDraw


FANZ_EMOJI_PATH = (
    Path(settings.BASE_DIR)
    / "static"
    / "img"
    / "fanz-star-struck.png"
)


def _load_fanz_emoji(size):
    """
    Load the FANZ star-struck emoji and resize it cleanly.
    """
    if not FANZ_EMOJI_PATH.exists():
        raise FileNotFoundError(
            f"FANZ QR emoji was not found: {FANZ_EMOJI_PATH}"
        )

    emoji = Image.open(FANZ_EMOJI_PATH).convert("RGBA")

    emoji.thumbnail(
        (size, size),
        Image.Resampling.LANCZOS,
    )

    return emoji


def make_branded_referral_qr(data):
    """
    Create a high-error-correction referral QR with
    the FANZ star-struck emoji centered inside it.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )

    qr.add_data(data)
    qr.make(fit=True)

    qr_image = qr.make_image(
        fill_color="black",
        back_color="white",
    ).convert("RGBA")

    qr_width, qr_height = qr_image.size

    # Total protected badge area.
    badge_size = int(qr_width * 0.22)

    if badge_size % 2:
        badge_size += 1

    badge = Image.new(
        "RGBA",
        (badge_size, badge_size),
        (0, 0, 0, 0),
    )

    badge_draw = ImageDraw.Draw(badge)

    # White circular background protects the emoji
    # from the black QR modules underneath.
    badge_draw.ellipse(
        (
            0,
            0,
            badge_size - 1,
            badge_size - 1,
        ),
        fill=(255, 255, 255, 255),
    )

    # Purple inner ring keeps the FANZ branding visible.
    ring_padding = max(
        2,
        int(badge_size * 0.055),
    )

    badge_draw.ellipse(
        (
            ring_padding,
            ring_padding,
            badge_size - ring_padding - 1,
            badge_size - ring_padding - 1,
        ),
        fill=(124, 58, 237, 255),
    )

    # Leave some purple ring visible around the emoji.
    emoji_size = int(badge_size * 0.78)
    emoji = _load_fanz_emoji(emoji_size)

    emoji_position = (
        (badge_size - emoji.width) // 2,
        (badge_size - emoji.height) // 2,
    )

    badge.alpha_composite(
        emoji,
        dest=emoji_position,
    )

    badge_position = (
        (qr_width - badge_size) // 2,
        (qr_height - badge_size) // 2,
    )

    qr_image.alpha_composite(
        badge,
        dest=badge_position,
    )

    return qr_image.convert("RGB")
