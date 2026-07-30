from .models import Event


def get_discovery_events(hub, limit=12):
    """
    Return public events belonging to active businesses in a Discovery Hub.

    Events inherit Discovery Hub membership through their related business.
    The queryset is reusable by Discovery pages, APIs, search, syndication,
    metrics, and future AI context retrieval.
    """
    return (
        Event.objects
        .filter(
            business__discovery_hub=hub,
            business__is_active=True,
            is_published=True,
            is_cancelled=False,
        )
        .select_related(
            "creator",
            "business",
            "business__discovery_hub",
        )
        .order_by("start_at")[:limit]
    )
