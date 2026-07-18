from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Count
from .forms import BusinessListingForm, BusinessUpdateForm
from .models import BusinessFan, BusinessListing, BusinessUpdate


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

    featured_update = (
        business.updates
        .filter(
            is_published=True,
            is_featured=True,
        )
        .order_by("-created_at")
        .first()
    )

    updates = (
        business.updates
        .filter(is_published=True)
        .order_by("-is_featured", "-created_at")
    )

    fan_count = business.fans.count()
    event_count = business.events.count()
    update_count = business.updates.filter(
        is_published=True,
    ).count()

    return render(
        request,
        "businesses/business_detail.html",
        {
            "business": business,
            "is_fan": is_fan,
            "featured_update": featured_update,
            "updates": updates,
            "fan_count": fan_count,
            "event_count": event_count,
            "update_count": update_count,
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

@login_required
def my_businesses(request):
    businesses = (
        BusinessListing.objects
        .filter(
            owner=request.user,
            is_active=True,
        )
        .annotate(
            fan_count=Count(
                "fans",
                distinct=True,
            ),
            event_count=Count(
                "events",
                distinct=True,
            ),
            update_count=Count(
                "updates",
                distinct=True,
            ),
        )
        .order_by("name")
    )

    return render(
        request,
        "businesses/my_businesses.html",
        {
            "businesses": businesses,
        },
    )

@login_required
def business_edit(request, slug):
    business = get_object_or_404(
        BusinessListing,
        slug=slug,
        owner=request.user,
    )

    if request.method == "POST":
        form = BusinessListingForm(
            request.POST,
            request.FILES,
            instance=business,
            is_edit=True,
        )

        if form.is_valid():
            business = form.save()

            messages.success(
                request,
                "Your business was updated successfully.",
            )

            return redirect(
                "businesses:detail",
                slug=business.slug,
            )
    else:
        form = BusinessListingForm(
            instance=business,
            is_edit=True,
        )

    return render(
        request,
        "businesses/business_form.html",
        {
            "form": form,
            "business": business,
            "is_edit": True,
        },
    )


@login_required
def publish_business_update(request, slug):
    business = get_object_or_404(
        BusinessListing,
        slug=slug,
        owner=request.user,
    )

    if request.method == "POST":
        form = BusinessUpdateForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            update = form.save(commit=False)

            update.business = business
            update.author = request.user
            update.is_published = True

            if update.is_featured:
                BusinessUpdate.objects.filter(
                    business=business,
                    is_featured=True,
                ).update(is_featured=False)

            update.save()

            messages.success(
                request,
                "Business update published successfully.",
            )

            return redirect(
                "businesses:detail",
                slug=business.slug,
            )
    else:
        form = BusinessUpdateForm()

    return render(
        request,
        "businesses/business_update_form.html",
        {
            "business": business,
            "form": form,
        },
    )
