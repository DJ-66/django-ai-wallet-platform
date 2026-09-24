from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .feed_publishing import publish_feed_post
from .models import (
    CreatorEdgePublicationReceipt,
    CreatorEdgeRegistration,
)


class CreatorEdgePublicationError(RuntimeError):
    pass


def _normalize_publication_key(value):
    key = str(value or "").strip()

    if not key:
        raise CreatorEdgePublicationError(
            "publication_key is required."
        )

    if len(key) > 160:
        raise CreatorEdgePublicationError(
            "publication_key must be 160 characters or fewer."
        )

    return key


def _creator_for_edge(edge):
    founder = edge.founder_account

    creator = founder.current_account

    if creator is None:
        raise CreatorEdgePublicationError(
            "TG Edge Founder account has no current FANZ operator."
        )

    if not creator.is_active:
        raise CreatorEdgePublicationError(
            "TG Edge FANZ operator is not active."
        )

    return creator


@transaction.atomic
def publish_creator_edge_feed_post(
    *,
    edge_id,
    publication_key,
    title="",
    content="",
    uploaded_media=None,
    is_public=True,
    is_paid=False,
    unlock_price=0,
):
    """
    Idempotently publish one FANZ FeedPost for an authenticated
    creator-operated TG Edge.

    Authentication happens before this service is called. This
    service owns creator resolution, publication idempotency, and
    native FANZ feed publication.

    Reusing publication_key returns the original FeedPost rather
    than creating another post.
    """

    key = _normalize_publication_key(
        publication_key
    )

    try:
        edge = (
            CreatorEdgeRegistration.objects
            .select_for_update(
                of=("self",)
            )
            .select_related(
                "founder_account__current_account"
            )
            .get(edge_id=edge_id)
        )
    except CreatorEdgeRegistration.DoesNotExist as exc:
        raise CreatorEdgePublicationError(
            "TG Edge registration does not exist."
        ) from exc

    if (
        edge.status
        != CreatorEdgeRegistration.STATUS_ACTIVE
    ):
        raise CreatorEdgePublicationError(
            "TG Edge registration is not active."
        )

    existing = (
        CreatorEdgePublicationReceipt.objects
        .select_related(
            "feed_post",
            "creator",
            "edge",
        )
        .filter(publication_key=key)
        .first()
    )

    if existing is not None:
        if existing.edge_id != edge.pk:
            raise CreatorEdgePublicationError(
                "publication_key belongs to another TG Edge."
            )

        return existing.feed_post, False

    creator = _creator_for_edge(edge)

    uploads = (
        [uploaded_media]
        if uploaded_media is not None
        else []
    )

    try:
        post = publish_feed_post(
            user=creator,
            title=title,
            content=content,
            uploads=uploads,
            is_public=is_public,
            is_paid=is_paid,
            unlock_price=unlock_price,
        )
    except ValidationError as exc:
        raise CreatorEdgePublicationError(
            str(exc)
        ) from exc

    try:
        CreatorEdgePublicationReceipt.objects.create(
            edge=edge,
            publication_key=key,
            creator=creator,
            feed_post=post,
        )
    except IntegrityError as exc:
        raise CreatorEdgePublicationError(
            "publication receipt could not be recorded."
        ) from exc

    return post, True
