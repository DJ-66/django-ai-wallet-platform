"""Approved campaign destinations for FANZ AutoPost."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from django.urls import reverse


@dataclass(frozen=True)
class CampaignDestination:
    campaign: str
    url: str
    affiliate_code: str | None
    purchase_attribution_ready: bool = False


def resolve_campaign_destination(
    *,
    campaign: str,
    affiliate_code: str | None = None,
    custom_url: str | None = None,
) -> CampaignDestination:
    """Resolve a destination without claiming a referral sale."""

    if campaign == "founder":
        url = reverse("founder_tienda")

    elif campaign == "credits":
        url = reverse(
            "public_profile_root",
            kwargs={"username": "BuyCredits"},
        )

    elif campaign == "autopost":
        url = reverse(
            "public_profile_root",
            kwargs={"username": "autoPoster"},
        )

    elif campaign == "custom":
        if not custom_url:
            raise ValueError("Custom business URL is required")

        url = custom_url.strip()
        parsed = urlsplit(url)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or any(c.isspace() or ord(c) < 32 for c in url)
            or parsed.hostname in {"localhost"}
        ):
            raise ValueError("Invalid custom business URL")

        # Preliminary validation only. Public release will also
        # require domain/IP safety and redirect checks.

    else:
        raise ValueError("Unknown AutoPost campaign")

    return CampaignDestination(
        campaign=campaign,
        url=url,
        affiliate_code=(
            affiliate_code if campaign != "custom" else None
        ),
    )
