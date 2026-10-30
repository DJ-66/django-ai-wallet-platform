"""Read-only FANZ mention destination resolution."""

from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET

from auctions.models import FounderAccount
from auctions.validators import (
    normalize_founder_handle,
    is_valid_founder_handle,
)


@require_GET
def resolve_mention(request, username):
    """Resolve a mention without creating reservations or wallet holds."""

    profile_url = reverse(
        "public_profile_root",
        kwargs={"username": username},
    )

    # Existing accounts retain their normal profile destination.
    if User.objects.filter(username__iexact=username).exists():
        return redirect(profile_url)

    handle = normalize_founder_handle(username)

    # Dynamic vending supports only 3-4 character Founder handles.
    if not (
        3 <= len(handle) <= 4
        and is_valid_founder_handle(handle)
    ):
        return redirect(profile_url)

    founder = FounderAccount.objects.filter(
        handle=handle,
    ).first()

    # Never advertise an already owned, listed, or reserved
    # Founder property as available for vending.
    if founder is not None:
        if (
            founder.owner_root_id is not None
            or founder.status not in {
                FounderAccount.STATUS_AVAILABLE,
                FounderAccount.STATUS_TREASURY,
            }
        ):
            return redirect(profile_url)

    query = urlencode({
        "handle": handle,
        "budget": "300",
    })

    tienda_url = reverse("founder_tienda")

    return HttpResponseRedirect(
        f"{tienda_url}?{query}#founder-vending"
    )
