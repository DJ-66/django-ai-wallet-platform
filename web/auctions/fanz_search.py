from django.contrib.auth.models import User
from django.db.models import Q
from django.urls import reverse

from businesses.models import BusinessListing

from .models import (
    Auction,
    DiscoveryHub,
    Event,
    FeedPost,
    FounderAccount,
    Hashtag,
)


DEFAULT_LIMIT_PER_TYPE = 5
MAX_LIMIT_PER_TYPE = 20
CANDIDATE_MULTIPLIER = 5

SUPPORTED_LANGUAGES = ("en", "es", "pt")
DEFAULT_LANGUAGE = "en"


def _normalize_language(language):
    language = (language or DEFAULT_LANGUAGE).strip().lower()

    if "-" in language:
        language = language.split("-", 1)[0]

    if language not in SUPPORTED_LANGUAGES:
        return DEFAULT_LANGUAGE

    return language

def _clean_query(query):
    """
    Normalize user input while preserving the original query
    for presentation/debugging.
    """
    return (query or "").strip()


def _bare_query(query):
    """
    Remove one FANZ object prefix for canonical matching.

    @alex -> alex
    #food -> food
    """
    query = _clean_query(query)

    if query.startswith(("@", "#")):
        return query[1:].strip()

    return query


def _limit(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT_PER_TYPE

    return max(
        1,
        min(value, MAX_LIMIT_PER_TYPE),
    )


def _candidate_limit(limit):
    """
    Pull a slightly wider deterministic candidate set,
    then rank it consistently in Python.
    """
    return min(
        limit * CANDIDATE_MULTIPLIER,
        MAX_LIMIT_PER_TYPE * CANDIDATE_MULTIPLIER,
    )


def _match_text(
    value,
    query,
    *,
    exact=100,
    startswith=75,
    contains=50,
):
    """
    Score one text value against a normalized query.
    """
    value = (value or "").strip().casefold()
    query = (query or "").strip().casefold()

    if not value or not query:
        return 0

    if value == query:
        return exact

    if value.startswith(query):
        return startswith

    if query in value:
        return contains

    return 0


def _best_match(query, fields):
    """
    fields is a sequence of:

        (
            field_name,
            value,
            exact_score,
            startswith_score,
            contains_score,
        )

    Returns:
        (best_score, match_reason)
    """
    best_score = 0
    best_reason = ""

    for (
        field_name,
        value,
        exact_score,
        startswith_score,
        contains_score,
    ) in fields:
        score = _match_text(
            value,
            query,
            exact=exact_score,
            startswith=startswith_score,
            contains=contains_score,
        )

        if score > best_score:
            best_score = score
            best_reason = field_name

    return best_score, best_reason


def _normalized_result(
    *,
    object_type,
    object_id,
    title,
    subtitle,
    url,
    score,
    match_reason,
    **extra,
):
    """
    Common Phase 12 search-result contract.
    """
    result = {
        "type": object_type,
        "id": object_id,
        "title": title or "",
        "subtitle": subtitle or "",
        "url": url,
        "score": int(score or 0),
        "match_reason": match_reason or "",
    }

    result.update(extra)

    return result


def _rank_results(results, limit):
    """
    Stable deterministic ordering inside one object family.
    """
    return sorted(
        results,
        key=lambda row: (
            -row["score"],
            row["title"].casefold(),
            row["id"],
        ),
    )[:limit]


def _search_users(query, limit):
    rows = (
        User.objects
        .filter(
            Q(username__icontains=query)
            | Q(profile__display_name__icontains=query)
            | Q(profile__bio__icontains=query)
            | Q(profile__location__icontains=query)
        )
        .select_related("profile")
        .distinct()
        .order_by("username")[
            :_candidate_limit(limit)
        ]
    )

    results = []

    for user in rows:
        profile = getattr(user, "profile", None)

        display_name = (
            profile.display_name
            if profile
            else ""
        )

        bio = (
            profile.bio
            if profile
            else ""
        )

        location = (
            profile.location
            if profile
            else ""
        )

        score, reason = _best_match(
            query,
            [
                (
                    "username",
                    user.username,
                    100,
                    75,
                    50,
                ),
                (
                    "display_name",
                    display_name,
                    95,
                    70,
                    45,
                ),
                (
                    "bio",
                    bio,
                    40,
                    35,
                    30,
                ),
                (
                    "location",
                    location,
                    35,
                    30,
                    25,
                ),
            ],
        )

        if score == 0:
            continue

        if profile:
            result_url = reverse(
                "public_profile",
                kwargs={
                    "username": user.username,
                },
            )
        else:
            result_url = (
                reverse("fanz_search")
                + f"?q=%40{user.username}"
            )

        results.append(
            _normalized_result(
                object_type="user",
                object_id=user.pk,
                title=f"@{user.username}",
                subtitle=display_name,
                subtitle_code=(
                    ""
                    if display_name
                    else "fanz_account"
                ),
                url=result_url,
                score=score,
                match_reason=reason,
                has_profile=bool(profile),
            )
        )

    return _rank_results(results, limit)


def _search_founder_accounts(query, limit):
    rows = (
        FounderAccount.objects
        .filter(
            handle__icontains=query,
        )
        .order_by(
            "handle_length",
            "handle",
        )[
            :_candidate_limit(limit)
        ]
    )

    results = []

    for asset in rows:
        score, reason = _best_match(
            query,
            [
                (
                    "handle",
                    asset.handle,
                    100,
                    75,
                    50,
                ),
            ],
        )

        results.append(
            _normalized_result(
                object_type="founder_account",
                object_id=asset.pk,
                title=f"@{asset.handle}",
                subtitle="",
                subtitle_code="founder_property",
                url=reverse("founder_tienda"),
                score=score,
                match_reason=reason,
                status=asset.status,
            )
        )

    return _rank_results(results, limit)


def _search_hashtags(query, limit):
    rows = (
        Hashtag.objects
        .filter(
            name__icontains=query,
        )
        .order_by(
            "-usage_count",
            "name",
        )[
            :_candidate_limit(limit)
        ]
    )

    results = []

    for hashtag in rows:
        score, reason = _best_match(
            query,
            [
                (
                    "hashtag",
                    hashtag.name,
                    100,
                    75,
                    50,
                ),
            ],
        )

        results.append(
            _normalized_result(
                object_type="hashtag",
                object_id=hashtag.pk,
                title=f"#{hashtag.name}",
                subtitle="",
                subtitle_code="hashtag_uses",
                subtitle_count=hashtag.usage_count,
                url=reverse(
                    "hashtag_feed",
                    kwargs={
                        "tag_name": hashtag.name,
                    },
                ),
                score=score,
                match_reason=reason,
                usage_count=hashtag.usage_count,
            )
        )

    return _rank_results(results, limit)


def _search_posts(query, limit):
    rows = (
        FeedPost.objects
        .filter(
            is_public=True,
        )
        .filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(hashtags__name__icontains=query)
        )
        .select_related("user")
        .prefetch_related("hashtags")
        .distinct()
        .order_by("-created_at")[
            :_candidate_limit(limit)
        ]
    )

    results = []

    for post in rows:
        hashtag_names = [
            hashtag.name
            for hashtag in post.hashtags.all()
        ]

        hashtag_blob = " ".join(hashtag_names)

        score, reason = _best_match(
            query,
            [
                (
                    "title",
                    post.title,
                    95,
                    75,
                    55,
                ),
                (
                    "hashtag",
                    hashtag_blob,
                    85,
                    70,
                    55,
                ),
                (
                    "content",
                    post.content,
                    45,
                    40,
                    35,
                ),
            ],
        )

        title = (
            post.title.strip()
            if post.title
            else post.content[:80].strip()
        )

        results.append(
            _normalized_result(
                object_type="post",
                object_id=post.pk,
                title=title,
                subtitle=f"@{post.user.username}",
                url=reverse(
                    "post_detail",
                    kwargs={
                        "post_id": post.pk,
                    },
                ),
                score=score,
                match_reason=reason,
            )
        )

    return _rank_results(results, limit)


def _search_discovery_hubs(query, limit):
    rows = (
        DiscoveryHub.objects
        .filter(
            is_active=True,
        )
        .filter(
            Q(hashtag__icontains=query)
            | Q(title__icontains=query)
            | Q(subtitle__icontains=query)
        )
        .order_by(
            "sort_order",
            "title",
        )[
            :_candidate_limit(limit)
        ]
    )

    results = []

    for hub in rows:
        score, reason = _best_match(
            query,
            [
                (
                    "hashtag",
                    hub.hashtag,
                    100,
                    80,
                    60,
                ),
                (
                    "title",
                    hub.title,
                    95,
                    75,
                    55,
                ),
                (
                    "subtitle",
                    hub.subtitle,
                    40,
                    35,
                    30,
                ),
            ],
        )

        results.append(
            _normalized_result(
                object_type="discovery_hub",
                object_id=hub.pk,
                title=hub.title,
                subtitle=hub.subtitle[:120],
                url=reverse(
                    "discovery_hub_detail",
                    kwargs={
                        "slug": hub.slug,
                    },
                ),
                score=score,
                match_reason=reason,
            )
        )

    return _rank_results(results, limit)


def _search_auctions(query, limit):
    rows = (
        Auction.objects
        .exclude(status="draft")
        .filter(
            Q(title__icontains=query)
            | Q(hashtags__name__icontains=query)
            | Q(translations__title__icontains=query)
            | Q(translations__description__icontains=query)
        )
        .prefetch_related(
            "hashtags",
            "translations",
        )
        .distinct()
        .order_by("-created_at")[
            :_candidate_limit(limit)
        ]
    )

    results = []

    for auction in rows:
        hashtag_blob = " ".join(
            hashtag.name
            for hashtag in auction.hashtags.all()
        )

        translation_titles = " ".join(
            translation.title
            for translation in auction.translations.all()
            if translation.title
        )

        translation_descriptions = " ".join(
            translation.description
            for translation in auction.translations.all()
            if translation.description
        )

        score, reason = _best_match(
            query,
            [
                (
                    "title",
                    auction.title,
                    95,
                    75,
                    50,
                ),
                (
                    "hashtag",
                    hashtag_blob,
                    80,
                    65,
                    50,
                ),
                (
                    "translated_title",
                    translation_titles,
                    80,
                    65,
                    45,
                ),
                (
                    "translated_description",
                    translation_descriptions,
                    35,
                    30,
                    25,
                ),
            ],
        )

        results.append(
            _normalized_result(
                object_type="auction",
                object_id=auction.pk,
                title=auction.title,
                subtitle="",
                subtitle_code="auction_status",
                subtitle_status=auction.status,
                url=reverse(
                    "auction_detail",
                    kwargs={
                        "auction_id": auction.pk,
                    },
                ),
                score=score,
                match_reason=reason,
                status=auction.status,
            )
        )

    return _rank_results(results, limit)


def _search_events(query, limit):
    rows = (
        Event.objects
        .filter(
            is_published=True,
            is_cancelled=False,
        )
        .filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(location__icontains=query)
        )
        .order_by(
            "start_at",
            "title",
        )[
            :_candidate_limit(limit)
        ]
    )

    results = []

    for event in rows:
        score, reason = _best_match(
            query,
            [
                (
                    "title",
                    event.title,
                    95,
                    75,
                    50,
                ),
                (
                    "location",
                    event.location,
                    55,
                    45,
                    40,
                ),
                (
                    "description",
                    event.description,
                    40,
                    35,
                    30,
                ),
            ],
        )

        results.append(
            _normalized_result(
                object_type="event",
                object_id=event.pk,
                title=event.title,
                subtitle=event.location,
                url=reverse(
                    "event_detail",
                    kwargs={
                        "event_id": event.pk,
                    },
                ),
                score=score,
                match_reason=reason,
            )
        )

    return _rank_results(results, limit)


def _search_businesses(query, limit):
    rows = (
        BusinessListing.objects
        .filter(
            is_active=True,
        )
        .filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(address__icontains=query)
            | Q(city__icontains=query)
            | Q(country__icontains=query)
        )
        .order_by("name")[
            :_candidate_limit(limit)
        ]
    )

    results = []

    for business in rows:
        score, reason = _best_match(
            query,
            [
                (
                    "name",
                    business.name,
                    100,
                    75,
                    50,
                ),
                (
                    "city",
                    business.city,
                    55,
                    45,
                    40,
                ),
                (
                    "country",
                    business.country,
                    50,
                    40,
                    35,
                ),
                (
                    "address",
                    business.address,
                    40,
                    35,
                    30,
                ),
                (
                    "description",
                    business.description,
                    35,
                    30,
                    25,
                ),
            ],
        )

        subtitle = " · ".join(
            part
            for part in [
                business.city,
                business.country,
            ]
            if part
        )

        results.append(
            _normalized_result(
                object_type="business",
                object_id=business.pk,
                title=business.name,
                subtitle=subtitle,
                url=reverse(
                    "businesses:detail",
                    kwargs={
                        "slug": business.slug,
                    },
                ),
                score=score,
                match_reason=reason,
                industry=business.industry,
            )
        )

    return _rank_results(results, limit)


def search_fanz(
    query,
    *,
    viewer=None,
    language="en",
    limit_per_type=DEFAULT_LIMIT_PER_TYPE,
):
    """
    Phase 12 deterministic FANZ retrieval.

    Retrieval determines canonical truth.
    Language controls presentation later.

    No LLM is involved here.
    """

    raw_query = _clean_query(query)
    query = _bare_query(raw_query)
    limit = _limit(limit_per_type)
    language = _normalize_language(language)

    if not query:
        return {
            "query": raw_query,
            "normalized_query": "",
            "language": language,
            "total": 0,
            "results": [],
            "groups": {},
        }

    groups = {
        "users": _search_users(
            query,
            limit,
        ),
        "founder_accounts": _search_founder_accounts(
            query,
            limit,
        ),
        "hashtags": _search_hashtags(
            query,
            limit,
        ),
        "posts": _search_posts(
            query,
            limit,
        ),
        "discovery_hubs": _search_discovery_hubs(
            query,
            limit,
        ),
        "auctions": _search_auctions(
            query,
            limit,
        ),
        "events": _search_events(
            query,
            limit,
        ),
        "businesses": _search_businesses(
            query,
            limit,
        ),
    }

    results = []

    for group_name, group_results in groups.items():
        for result in group_results:
            result["group"] = group_name
            results.append(result)

    results.sort(
        key=lambda row: (
            -row["score"],
            row["title"].casefold(),
            row["type"],
            row["id"],
        )
    )

    return {
        "query": raw_query,
        "normalized_query": query,
        "language": language,
        "total": len(results),
        "results": results,
        "groups": groups,
    }
