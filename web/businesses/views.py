from django.shortcuts import get_object_or_404, render

from .models import BusinessListing


def business_detail(request, slug):
    business = get_object_or_404(
        BusinessListing.objects.select_related("discovery_hub"),
        slug=slug,
        is_active=True,
    )

    return render(
        request,
        "businesses/business_detail.html",
        {
            "business": business,
        },
    )
