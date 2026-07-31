from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import FeedPost, Hashtag, UserProfile
from .wallet_setup import provision_user_wallet


@receiver(user_signed_up)
def provision_wallet_for_new_user(request, user, **kwargs):
    referral_code = None

    if request:
        referral_code = (
            request.GET.get("ref")
            or request.session.get("referral_code")
        )

    provision_user_wallet(
        user,
        referral_code=referral_code,
    )


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
        )


@receiver(m2m_changed, sender=FeedPost.hashtags.through)
def update_hashtag_usage_counts(
    sender,
    instance,
    action,
    reverse,
    model,
    pk_set,
    **kwargs,
):
    """
    Keep stored hashtag post counts synchronized when FeedPost
    hashtag relationships are added, removed, or cleared.
    """
    cache_attribute = "_affected_hashtag_ids"

    if action == "pre_clear":
        if reverse:
            affected_ids = [instance.pk]
        else:
            affected_ids = list(
                instance.hashtags.values_list(
                    "pk",
                    flat=True,
                )
            )

        setattr(
            instance,
            cache_attribute,
            affected_ids,
        )
        return

    if action not in {
        "post_add",
        "post_remove",
        "post_clear",
    }:
        return

    if action == "post_clear":
        affected_ids = getattr(
            instance,
            cache_attribute,
            [],
        )
    elif reverse:
        affected_ids = [instance.pk]
    else:
        affected_ids = list(pk_set or [])

    for hashtag in Hashtag.objects.filter(
        pk__in=affected_ids
    ):
        hashtag.usage_count = hashtag.posts.count()
        hashtag.save(
            update_fields=["usage_count"]
        )

    if hasattr(instance, cache_attribute):
        delattr(
            instance,
            cache_attribute,
        )
