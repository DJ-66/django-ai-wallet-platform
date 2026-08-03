import random

from auctions.models import Notification
from .models import BusinessFan, BusinessListing

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


def process_business_referral_activation(*, user, wallet):
    """
    Convert a pending referral business into a BusinessFan relationship.

    Returns True only when a new BusinessFan relationship is created.
    """
    business = wallet.pending_referral_business

    if not business:
        return False

    fan_created = False

    if (
        business.is_active
        and business.owner == wallet.referred_by
        and business.owner != user
    ):
        _, fan_created = BusinessFan.objects.get_or_create(
            business=business,
            fan=user,
        )

        if fan_created:
            owner_message_bank = [
                (
                    f"@{user.username} became a FAN of "
                    f"{business.name} ❤️"
                ),
                (
                    f"{business.name} gained a new FAN: "
                    f"@{user.username} 🤩"
                ),
                (
                    f"Welcome @{user.username} to "
                    f"{business.name}'s FANZ 🎉"
                ),
            ]

            new_fan_message_bank = [
                (
                    f"You're now one of "
                    f"{business.name}'s FANZ ❤️"
                ),
                (
                    f"Welcome to {business.name}'s FANZ, "
                    f"@{user.username} 🤩"
                ),
                (
                    f"Thanks for supporting "
                    f"{business.name} 💜"
                ),
            ]

            Notification.objects.create(
                user=business.owner,
                actor=user,
                notification_type=Notification.FAN,
                message=random.choice(
                    owner_message_bank
                )[:255],
            )

            Notification.objects.create(
                user=user,
                actor=business.owner,
                notification_type=Notification.FAN,
                message=random.choice(
                    new_fan_message_bank
                )[:255],
            )

    wallet.pending_referral_business = None
    wallet.save(
        update_fields=[
            "pending_referral_business",
        ]
    )

    return fan_created
