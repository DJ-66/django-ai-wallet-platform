from django.utils import timezone
from businesses.services import get_discovery_business_count
from .models import Event
from .services import get_public_hashtag_post_count

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
    }
