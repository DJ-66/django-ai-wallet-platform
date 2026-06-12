from .models import BidWallet
from .models import Notification


def wallet_context(request):
    if request.user.is_authenticated:
        wallet, _ = BidWallet.objects.get_or_create(
            user=request.user
        )

        return {
            "wallet": wallet
        }

    return {
        "wallet": None
    }


def notifications(request):
    if not request.user.is_authenticated:
        return {
            "unread_notification_count": 0,
        }

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    return {
        "unread_notification_count": unread_count,
    }
