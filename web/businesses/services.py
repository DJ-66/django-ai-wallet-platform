from .models import BusinessListing


def _get_discovery_business_queryset(hub):
    """
    Build the shared queryset for active businesses assigned to a
    Discovery Hub.

    Keep Discovery eligibility rules here so listing and metric
    capabilities cannot drift apart.
    """
    return BusinessListing.objects.filter(
        discovery_hub=hub,
        is_active=True,
    )


def get_discovery_businesses(hub, limit=12):
    """
    Return active business profiles assigned to a Discovery Hub.

    The queryset is reusable by Discovery pages, APIs, search,
    syndication, and future AI context retrieval.
    """
    queryset = (
        _get_discovery_business_queryset(hub)
        .select_related(
            "owner",
            "discovery_hub",
        )
        .prefetch_related(
            "fans",
            "media",
        )
        .order_by("-updated_at", "name")
    )

    if limit is not None:
        queryset = queryset[:limit]

    return queryset


def get_discovery_business_count(hub):
    """
    Return the total number of active business profiles assigned
    to a Discovery Hub.
    """
    return _get_discovery_business_queryset(hub).count()
