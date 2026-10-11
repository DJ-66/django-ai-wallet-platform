"""Prepare approved multilingual FANZ promotional campaign media."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from core.image_utils import process_fanz_image_upload

from auctions.promotional_campaigns import (
    CAMPAIGNS,
    get_campaign_copy,
    get_campaign_caption,
)
from auctions.promotional_overlays import (
    render_promotional_overlay,
)


LANGUAGES = ("en", "es", "pt")


@dataclass(frozen=True)
class PreparedCampaignImage:
    language: str
    headline: str
    cta: str
    content: str
    image_bytes: bytes


def prepare_promotional_campaign(publication, asset):
    """
    Prepare EN/ES/PT promotional images without database writes.

    Restricted offers remain disabled.
    The original media asset is never modified.
    """

    campaign_key = publication.campaign_key

    if not campaign_key:
        raise ValidationError(
            "Publication has no promotional campaign."
        )

    campaign = CAMPAIGNS.get(campaign_key)

    if campaign is None:
        raise ValidationError(
            "Unknown promotional campaign."
        )

    if campaign.requires_offer_verification:
        raise ValidationError(
            "Promotional offer is not yet approved."
        )

    if asset.account_id != publication.creator_id:
        raise ValidationError(
            "Promotional media belongs to another account."
        )

    if not asset.is_active:
        raise ValidationError(
            "Promotional media is inactive."
        )

    if not asset.image.name or not asset.image.storage.exists(
        asset.image.name
    ):
        raise ValidationError(
            "Promotional source image is missing."
        )

    referral_url = publication.referral_url

    # Validate the URL before rendering any images.
    from auctions.promotional_overlays import (
        _validate_referral_url,
    )

    try:
        _validate_referral_url(referral_url)
    except ValueError as exc:
        raise ValidationError(
            "Invalid promotional referral destination."
        ) from exc

    prepared = []

    for language in LANGUAGES:
        headline, cta = get_campaign_copy(
            campaign_key,
            language,
        )

        with asset.image.open("rb") as source:
            rendered = render_promotional_overlay(
                source,
                headline=headline,
                cta=cta,
                language=language,
                qr_url=referral_url,
            )

        prepared.append(
            PreparedCampaignImage(
                language=language,
                headline=headline,
                cta=cta,
                content=get_campaign_caption(
                    campaign_key,
                    language,
                ),
                image_bytes=rendered.read(),
            )
        )

    return prepared



def prepare_branded_translation(
    prepared_image,
    *,
    username,
):
    """
    Apply the standard FANZ footer to a localized image.

    The base English image is handled separately through
    publish_feed_post(), which already applies its footer.
    """

    upload = SimpleUploadedFile(
        f"promo-{prepared_image.language}.webp",
        prepared_image.image_bytes,
        content_type="image/webp",
    )

    processed = process_fanz_image_upload(
        upload,
        footer_text=f"❤ Fanz.to/{username}",
        max_width=1600,
        max_height=1600,
        quality=90,
    )

    return processed
