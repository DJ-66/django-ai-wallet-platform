import re
from .models import DiscoveryHub, Hashtag

HASHTAG_RE = re.compile(r"#([\w]{2,50})")

def extract_hashtag_names(text):
    if not text:
        return []

    names = []
    seen = set()

    for match in HASHTAG_RE.findall(text):
        name = match.lower().strip("_")

        if name and name not in seen:
            names.append(name)
            seen.add(name)

    return names

def get_or_create_hashtags(names):
    """
    Return Hashtag objects for normalized hashtag names.
    """
    tags = []

    for name in names:
        tag, _created = Hashtag.objects.get_or_create(name=name)
        tags.append(tag)

    return tags

def sync_post_hashtags(post):
    names = []
    seen = set()

    # Canonical post hashtags.
    canonical_names = extract_hashtag_names(
        f"{post.title} {post.content}"
    )

    for name in canonical_names:
        if name not in seen:
            names.append(name)
            seen.add(name)

    # Localized post hashtags.
    for translation in post.translations.all():
        translated_names = extract_hashtag_names(
            f"{translation.title} {translation.content}"
        )

        for name in translated_names:
            if name not in seen:
                names.append(name)
                seen.add(name)

    if not names:
        default_hub = (
            DiscoveryHub.objects
            .filter(slug="discover-fanz", is_active=True)
            .first()
        )

        names = [
            default_hub.hashtag
            if default_hub
            else "discover_fanz"
        ]

    old_tags = list(post.hashtags.all())
    tags = get_or_create_hashtags(names)

    post.hashtags.set(tags)

    affected_tags = set(old_tags + tags)

    for tag in affected_tags:
        tag.usage_count = (
            tag.posts.count()
            + tag.auctions.count()
        )
        tag.save(update_fields=["usage_count"])


def sync_auction_hashtags(auction, hashtag_text=""):
    """
    Assign explicit auction hashtags.

    If no explicit hashtags are supplied, fall back to hashtags
    found in the auction title. Auctions with no hashtags at all
    are assigned to #auctions.
    """
    names = extract_hashtag_names(hashtag_text)

    if not names:
        names = extract_hashtag_names(auction.title)

    if not names:
        default_hub = (
            DiscoveryHub.objects
            .filter(slug="auctions", is_active=True)
            .first()
        )
        names = [
            default_hub.hashtag
            if default_hub
            else "auctions"
        ]

    old_tags = list(auction.hashtags.all())
    tags = get_or_create_hashtags(names)

    auction.hashtags.set(tags)

    affected_tags = set(old_tags + tags)

    for tag in affected_tags:
        tag.usage_count = (
            tag.posts.count()
            + tag.auctions.count()
        )
        tag.save(update_fields=["usage_count"])
