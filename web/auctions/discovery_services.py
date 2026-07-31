from django.utils import timezone
from businesses.services import get_discovery_business_count
from .models import Auction, Event
from .services import get_public_hashtag_post_count
from .models import Auction, Event, Hashtag


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
