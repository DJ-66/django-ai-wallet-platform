from .models import BusinessListing


def get_discovery_businesses(hub, limit=12):
    """
    Return active business profiles assigned to a Discovery Hub.

    The queryset is reusable by Discovery pages, APIs, search,
    syndication, and future AI context retrieval.
    """
    return (
        BusinessListing.objects
        .filter(
            discovery_hub=hub,
            is_active=True,
        )
        .select_related(
            "owner",
            "discovery_hub",
        )
        .prefetch_related(
            "fans",
            "media",
        )
        .order_by("-updated_at", "name")[:limit]
    )
