from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from .models import UserProfile
from .wallet_setup import provision_user_wallet


@receiver(user_signed_up)
def provision_wallet_for_new_user(request, user, **kwargs):
    referral_code = None

    if request:
        referral_code = request.GET.get("ref") or request.session.get("referral_code")

    provision_user_wallet(user, referral_code=referral_code)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

