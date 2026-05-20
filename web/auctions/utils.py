from django.contrib.auth.models import User
from .models import BidWallet

SYSTEM_WALLET_USERNAME = "platform"


def get_system_wallet():
    user, _ = User.objects.get_or_create(
        username=SYSTEM_WALLET_USERNAME,
        defaults={
            "email": "platform@local"
        }
    )

    wallet, _ = BidWallet.objects.get_or_create(user=user)

    return wallet
