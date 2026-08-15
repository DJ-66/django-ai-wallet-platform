from django.utils import timezone
from businesses.services import get_discovery_business_count
from django.contrib.auth import get_user_model
from django.db.models import Max, Q
from .services import get_public_hashtag_post_count
from .models import (
    Auction,
    Event,
    FeedPost,
    Hashtag,
    UserProfileTranslation,
)

User = get_user_model()

def _get_discovery_event_queryset(hub):
    """
    Build the shared queryset for upcoming public events belonging
    to active businesses in a Discovery Hub.

    Keep Discovery eligibility rules here so listing and metric
    capabilities cannot drift apart.
    """
    return Event.objects.filter(
        business__discovery_hub=hub,
        business__is_active=True,
        is_published=True,
        is_cancelled=False,
        start_at__gte=timezone.now(),
    )


def get_discovery_events(hub, limit=12):
    """
    Return upcoming public events belonging to active businesses
    in a Discovery Hub.

    Events inherit Discovery Hub membership through their related business.
    The queryset is reusable by Discovery pages, APIs, search, syndication,
    metrics, and future AI context retrieval.
    """
    queryset = (
        _get_discovery_event_queryset(hub)
        .select_related(
            "creator",
            "business",
            "business__discovery_hub",
        )
        .order_by("start_at")
    )

    if limit is not None:
        queryset = queryset[:limit]

    return queryset



def get_discovery_event_count(hub):
    """
    Return the total number of upcoming public events belonging
    to active businesses in a Discovery Hub.
    """
    return _get_discovery_event_queryset(hub).count()

def get_live_hashtag_auctions(hashtag):
    """
    Return live platform auctions assigned to a hashtag.

    Results are ordered by ending soonest to reinforce scarcity.
    """
    now = timezone.now()

    return (
        Auction.objects
        .filter(
            hashtags=hashtag,
            status="live",
            starts_at__lte=now,
            ends_at__gt=now,
        )
        .prefetch_related(
            "hashtags",
            "media",
        )
        .order_by(
            "ends_at",
            "pk",
        )
        .distinct()
    )


def get_live_discovery_auctions(hub):
    """
    Return live platform auctions syndicated to a Discovery Hub.
    """
    hashtag_name = hub.hashtag.lstrip("#").strip().lower()

    hashtag = (
        Hashtag.objects
        .filter(name=hashtag_name)
        .first()
    )

    if hashtag is None:
        return Auction.objects.none()

    return get_live_hashtag_auctions(hashtag)


def get_live_discovery_auction_count(hub):
    """
    Return the number of live platform auctions syndicated to a
    Discovery Hub.
    """
    return get_live_discovery_auctions(hub).count()


def _get_discovery_creator_queryset(hub):
    """
    Build the shared queryset for creators with public posts connected
    to a Discovery Hub.

    Keep creator eligibility rules here so listings and metrics cannot
    drift apart.
    """
    hashtag_name = hub.hashtag.lstrip("#").strip().lower()

    hashtag = (
        Hashtag.objects
        .filter(name=hashtag_name)
        .first()
    )

    if hashtag is None:
        return User.objects.none()

    return (
        User.objects
        .filter(
            feedpost__hashtags=hashtag,
            feedpost__is_public=True,
        )
        .select_related("profile")
        .annotate(
            latest_discovery_post_at=Max(
                "feedpost__created_at",
                filter=Q(
                    feedpost__hashtags=hashtag,
                    feedpost__is_public=True,
                ),
            ),
        )
        .order_by(
            "-latest_discovery_post_at",
            "username",
        )
        .distinct()
    )

def get_discovery_creators(
    hub,
    limit=8,
    language="en",
):
    """
    Return creators with recent public posts connected to a Discovery Hub,
    including the localized profile bio for the requested language.
    """
    language = (
        language or "en"
    ).lower().split("-")[0]

    if language not in {
        "en",
        "es",
        "pt",
    }:
        language = "en"

    queryset = (
        _get_discovery_creator_queryset(
            hub
        )
    )

    if limit is not None:
        queryset = queryset[:limit]

    creators = list(queryset)

    for creator in creators:
        profile = creator.profile

        display_bio = profile.bio

        translation = (
            UserProfileTranslation.objects
            .filter(
                profile=profile,
                language=language,
            )
            .first()
        )

        if translation is not None:
            display_bio = translation.bio

        creator.display_bio = display_bio

    return creators


def get_discovery_creator_count(hub):
    """
    Return the number of creators with public posts connected to a
    Discovery Hub.
    """
    return _get_discovery_creator_queryset(hub).count()

def get_discovery_metrics(hub, hashtag=None):
    """
    Return live metrics for a Discovery Hub using shared capabilities.

    Metrics are calculated from current data and are not stored.
    """
    return {
        "posts": (
            get_public_hashtag_post_count(hashtag)
            if hashtag is not None
            else 0
        ),
        "creators": get_discovery_creator_count(hub),
        "businesses": get_discovery_business_count(hub),
        "events": get_discovery_event_count(hub),
        "auctions": get_live_discovery_auction_count(hub),

    }

def get_live_platform_auction_count():
    """
    Return the total number of currently live platform auctions.
    """
    now = timezone.now()

    return Auction.objects.filter(
        status="live",
        starts_at__lte=now,
        ends_at__gt=now,
    ).count()
