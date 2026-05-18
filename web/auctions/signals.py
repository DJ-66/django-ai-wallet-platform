from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from .wallet_setup import provision_user_wallet


@receiver(user_signed_up)
def provision_wallet_for_new_user(request, user, **kwargs):
    referral_code = None

    if request:
        referral_code = request.GET.get("ref") or request.session.get("referral_code")

    provision_user_wallet(user, referral_code=referral_code)
