from .models import BidWallet


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
