from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BusinessListingForm
from .models import BusinessFan, BusinessListing


def business_detail(request, slug):
    business = get_object_or_404(
        BusinessListing.objects.select_related(
            "discovery_hub",
            "owner",
        ),
        slug=slug,
        is_active=True,
    )

    is_fan = False

    if request.user.is_authenticated:
        is_fan = BusinessFan.objects.filter(
            business=business,
            fan=request.user,
        ).exists()

    updates = business.updates.filter(is_published=True)

    return render(
        request,
        "businesses/business_detail.html",
        {
            "business": business,
            "is_fan": is_fan,
            "updates": updates,
        },
    )


@login_required
def business_create(request):
    community_slug = request.GET.get("community", "").strip()
    community_business = None

    if community_slug:
        community_business = get_object_or_404(
            BusinessListing,
            slug=community_slug,
            is_claimed=False,
            is_active=True,
        )
    
    if request.method == "POST":
        form = BusinessListingForm(
            request.POST,
            request.FILES,
            instance=community_business,
        )

        if form.is_valid():
            business = form.save(commit=False)
            business.owner = request.user
            business.is_claimed = True
            business.is_active = True
            business.save()

            if community_business:
                messages.success(
                    request,
                    (
                        f"🎉 Congratulations! {business.name} is now "
                        "your FANZ business listing. Next, publish an "
                        "update, create your first event, and start "
                        "connecting with your community."
                    ),
                )
            else:
                messages.success(
                    request,
                    (
                        f"🎉 Congratulations! {business.name} is now "
                        "live on FANZ. Next, publish an update, create "
                        "your first event, and start connecting with "
                        "your community."
                    ),
                )

            return redirect(
                "businesses:detail",
                slug=business.slug,
            )
    else:
        form = BusinessListingForm(
            instance=community_business,
        )

    return render(
        request,
        "businesses/business_form.html",
        {
            "form": form,
            "community_business": community_business,
        },
    )


@login_required
def toggle_business_fan(request, slug):
    business = get_object_or_404(
        BusinessListing,
        slug=slug,
        is_active=True,
    )

    fan_relationship, created = BusinessFan.objects.get_or_create(
        business=business,
        fan=request.user,
    )

    if created:
        messages.success(
            request,
            f"⭐ You are now a fan of {business.name}!",
        )
    else:
        fan_relationship.delete()
        messages.success(
            request,
            f"You are no longer a fan of {business.name}.",
        )

    return redirect("businesses:detail", slug=business.slug)
