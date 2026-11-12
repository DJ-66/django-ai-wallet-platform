"""Labeled links for FANZ AutoPoster captions."""

from urllib.parse import urlsplit

from django.urls import reverse


CAMPAIGN_LABELS = {
    "founder": "Buy Your Name",
    "sponsor": "Support / Sponsor: The Fanz Platform",
    "credits": "Buy FANZ Credits",
    "autopost": "AutoPoster",
}


def labeled_link(label, url):
    """Create a Markdown link using an approved destination."""
    if not label or not url:
        raise ValueError("CTA label and URL are required")

    parsed = urlsplit(url)

    internal = (
        url.startswith("/")
        and not url.startswith("//")
    )

    external = (
        parsed.scheme == "https"
        and bool(parsed.hostname)
    )

    if not (internal or external):
        raise ValueError("Unsupported CTA URL")

    if any(char in label for char in "[]\n\r"):
        raise ValueError("Invalid CTA label")

    if any(char.isspace() for char in url):
        raise ValueError("Invalid CTA URL")

    return f"[{label}]({url})"


def creator_dm_link(username):
    """Generate a personalized FANZ messaging link."""
    if not username:
        raise ValueError("Creator username required")

    url = reverse(
        "start_conversation",
        kwargs={"username": username},
    )

    return labeled_link(
        "Direct Message Me, Now!",
        url,
    )


def campaign_link(campaign, destination):
    """Generate a labeled approved campaign link."""
    label = CAMPAIGN_LABELS.get(campaign)

    if label is None:
        raise ValueError("Unknown campaign")

    return labeled_link(label, destination.url)
