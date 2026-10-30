import os
from urllib.parse import quote, urlencode
from django.conf import settings
from auctions.qr_utils import make_branded_referral_qr
from auctions.wallet_setup import provision_user_wallet
import traceback
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.db import transaction
from auctions.registration_email_lock import (
    RegistrationEmailConflict,
    lock_registration_email,
)
from django.contrib.auth import get_user_model
from django.contrib import messages
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Count
from .forms_onboarding import GuestBusinessAccountForm
from .forms import (
    BusinessListingForm,
    BusinessMediaForm,
    BusinessUpdateForm,
)
from .models import (
    BusinessFan,
    BusinessListing,
    BusinessMedia,
    BusinessUpdate,
)


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

    now = timezone.now()

    featured_update = (
        business.updates
        .filter(
            is_published=True,
            is_featured=True,
            scheduled_for__lte=now,
        )
        .order_by("-created_at")
        .first()
    )

    updates = (
        business.updates
        .filter(
            is_published=True,
            scheduled_for__lte=now,
        )
        .order_by("-is_featured", "-created_at")
    )

    if featured_update:
        updates = updates.exclude(
            pk=featured_update.pk,
        )

    gallery_images = (
        business.media
        .filter(
            is_active=True,
            media_type=BusinessMedia.MEDIA_TYPE_IMAGE,
        )
        .order_by(
            "display_order",
            "-created_at",
        )
    )

    fan_count = business.fans.count()
    event_count = business.events.count()
    update_count = business.updates.filter(
        is_published=True,
        scheduled_for__lte=now,
    ).count()

    return render(
        request,
        "businesses/business_detail.html",
        {
            "business": business,
            "is_fan": is_fan,
            "featured_update": featured_update,
            "updates": updates,
            "gallery_images": gallery_images,
            "fan_count": fan_count,
            "event_count": event_count,
            "update_count": update_count,
        },
    )




def business_create(request):
    """List a business, creating a FANZ account for new visitors."""

    # Preserve referrals through GET -> form POST.
    if not request.user.is_authenticated:
        if request.GET.get("ref"):
            request.session["referral_code"] = request.GET["ref"]

        if request.GET.get("business"):
            request.session["referral_business_slug"] = (
                request.GET["business"]
            )

    authenticated = request.user.is_authenticated
    community_slug = request.GET.get("community", "").strip()
    community_business = None

    # Never permit an anonymous claim of an existing listing.
    if community_slug and authenticated:
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
        account_form = (
            None
            if authenticated
            else GuestBusinessAccountForm(request.POST, prefix="account")
        )

        valid_business = form.is_valid()
        valid_account = (
            True if account_form is None
            else account_form.is_valid()
        )

        if valid_business and valid_account:
            try:
                with transaction.atomic():
                    if authenticated:
                        owner = request.user
                    else:
                        lock_registration_email(
                            account_form.cleaned_data["email"]
                        )
                        owner = account_form.save(commit=False)
                        owner.set_password(
                            account_form.cleaned_data["password"]
                        )
                        owner.is_active = True
                        owner.save()

                        from auctions.models import NodeProfile
                        from auctions.wallet_setup import (
                            provision_user_wallet,
                        )

                        NodeProfile.objects.get_or_create(
                            user=owner,
                        )
                        referral_code = (
                            request.session.get("referral_code")
                            or request.GET.get("ref")
                        )

                        wallet = provision_user_wallet(
                            owner,
                            referral_code=referral_code,
                        )

                        referral_business_slug = (
                            request.session.get(
                                "referral_business_slug"
                            )
                            or request.GET.get("business")
                        )

                        if (
                            wallet.referred_by_id
                            and referral_business_slug
                        ):
                            referral_business = (
                                BusinessListing.objects.filter(
                                    slug=referral_business_slug,
                                    owner_id=wallet.referred_by_id,
                                    is_active=True,
                                ).first()
                            )

                            if referral_business:
                                wallet.pending_referral_business = (
                                    referral_business
                                )
                                wallet.save(
                                    update_fields=[
                                        "pending_referral_business",
                                    ]
                                )

                    business = form.save(commit=False)
                    business.owner = owner
                    business.is_claimed = True
                    business.is_active = True
                    business.save()

            except RegistrationEmailConflict:
                account_form.add_error(
                    "email",
                    "An account with this email already exists.",
                )
                return render(
                    request,
                    "businesses/business_form.html",
                    {
                        "form": form,
                        "account_form": account_form,
                        "community_business": community_business,
                    },
                    status=200,
                )

            if not authenticated:
                login(
                    request,
                    owner,
                    backend=(
                        "django.contrib.auth.backends.ModelBackend"
                    ),
                )
                request.session.pop("referral_code", None)
                request.session.pop(
                    "referral_business_slug", None
                )

            messages.success(
                request,
                f"🎉 {business.name} is now listed on FANZ!",
            )

            return redirect(
                "businesses:grow",
                slug=business.slug,
            )
    else:
        form = BusinessListingForm(
            instance=community_business,
        )
        account_form = (
            None
            if authenticated
            else GuestBusinessAccountForm(prefix="account")
        )

    return render(
        request,
        "businesses/business_form.html",
        {
            "form": form,
            "account_form": account_form,
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
def grow_business(request, slug):
    business = get_object_or_404(
        BusinessListing,
        slug=slug,
        owner=request.user,
        is_active=True,
    )

    wallet = provision_user_wallet(request.user)

    referral_query = urlencode(
    {
        "ref": wallet.referral_code,
        "business": business.slug,
    }
    )

    referral_url = (
        f"{request.scheme}://{request.get_host()}"
        f"/auctions/signup/?{referral_query}"
    )

    referral_qr_filename = (
        f"qr_codes/business_ref_"
        f"{business.pk}_{wallet.referral_code}.png"
    )

    referral_qr_path = os.path.join(
        settings.MEDIA_ROOT,
        referral_qr_filename,
    )

    os.makedirs(
        os.path.dirname(referral_qr_path),
        exist_ok=True,
    )

    expected_qr_url = referral_url

    regenerate_qr = not os.path.exists(referral_qr_path)

    if not regenerate_qr:
        # Regenerate when the campaign URL has changed.
        # The current implementation safely overwrites the image
        # whenever this Growth Center is loaded.
        regenerate_qr = True

    if regenerate_qr:
        qr_image = make_branded_referral_qr(
            expected_qr_url
        )
        qr_image.save(referral_qr_path)

    referral_qr_version = int(
        os.path.getmtime(referral_qr_path)
    )

    referral_qr_url = (
        f"{settings.MEDIA_URL}{referral_qr_filename}"
        f"?v={referral_qr_version}"
    )

    whatsapp_message = (
    f"{business.name}\n\n"
    f"Join our FANZ community Today\n\n"
    f"And we both get 50 FREE Credits!\n\n"
    f"Tap link to get started\n\n"
    f"{referral_url}"
    )

    whatsapp_share_url = (
        "https://wa.me/?text="
        f"{quote(whatsapp_message)}"
    )

    return render(
        request,
        "businesses/grow_business.html",
        {
            "business": business,
            "wallet": wallet,
            "referral_url": referral_url,
            "referral_qr_url": referral_qr_url,
            "whatsapp_share_url": whatsapp_share_url,

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

            now = timezone.now()
            release_interval = timedelta(hours=24)

            latest_queued_update = (
                BusinessUpdate.objects
                .filter(
                    business=business,
                    is_published=True,
                    scheduled_for__isnull=False,
                )
                .order_by("-scheduled_for")
                .first()
            )


            if latest_queued_update:
                next_available_time = (
                    latest_queued_update.scheduled_for
                    + release_interval
                )

                update.scheduled_for = max(
                    now,
                    next_available_time,
                )
            else:
                update.scheduled_for = now

            is_released_now = update.scheduled_for <= now

            if update.is_featured and is_released_now:
                BusinessUpdate.objects.filter(
                    business=business,
                    is_featured=True,
                ).update(is_featured=False)

            elif update.is_featured:
                update.is_featured = False

            update.save()

            if is_released_now:
                messages.success(
                    request,
                    "Business update published successfully.",
            )
            else:
                messages.success(
                    request,
                    (
                        "Business update saved and scheduled for "
                        f"{timezone.localtime(update.scheduled_for):%b %d, %Y at %I:%M %p}."
                    ),
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


@login_required
def delete_business_update(request, slug, update_id):
    business = get_object_or_404(
        BusinessListing,
        slug=slug,
        owner=request.user,
    )

    if request.method != "POST":
        return redirect(
            "businesses:detail",
            slug=business.slug,
        )

    update = get_object_or_404(
        BusinessUpdate,
        pk=update_id,
        business=business,
    )

    was_featured = update.is_featured

    update.delete()

    messages.success(
        request,
        "Business update deleted.",
    )

    return redirect(
        "businesses:detail",
        slug=business.slug,
    )


@login_required
def upload_business_media(request, slug):
    business = get_object_or_404(
        BusinessListing,
        slug=slug,
        owner=request.user,
        is_active=True,
    )

    current_media_count = business.media.filter(
        is_active=True,
    ).count()

    remaining_slots = max(
        0,
        16 - current_media_count,
    )

    max_upload_count = min(
        8,
        remaining_slots,
    )

    if request.method == "POST":
        form = BusinessMediaForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            images = form.cleaned_data["images"]

            if len(images) > remaining_slots:
                form.add_error(
                    "images",
                    (
                        f"This gallery has room for only "
                        f"{remaining_slots} more media item"
                        f"{'s' if remaining_slots != 1 else ''}. "
                        "A business gallery may contain a maximum "
                        "of 16 active images or videos."
                    ),
                )
            else:
                existing_max_order = (
                    business.media
                    .order_by("-display_order")
                    .values_list(
                        "display_order",
                        flat=True,
                    )
                    .first()
                )

                next_order = (
                    existing_max_order + 1
                    if existing_max_order is not None
                    else 0
                )

                for offset, image in enumerate(images):
                    BusinessMedia.objects.create(
                        business=business,
                        media_type=BusinessMedia.MEDIA_TYPE_IMAGE,
                        image=image,
                        caption="",
                        display_order=next_order + offset,
                        is_active=True,
                    )

                image_count = len(images)

                messages.success(
                    request,
                    (
                        f"{image_count} gallery image"
                        f"{'s' if image_count != 1 else ''} "
                        "uploaded successfully."
                    ),
                )

                return redirect(
                    "businesses:detail",
                    slug=business.slug,
                )
    else:
        form = BusinessMediaForm()

    return render(
        request,
        "businesses/business_media_form.html",
        {
            "business": business,
            "form": form,
            "current_media_count": current_media_count,
            "remaining_slots": remaining_slots,
            "max_upload_count": max_upload_count,
        },
    )


@login_required
def delete_business_media(request, slug):
    business = get_object_or_404(
        BusinessListing,
        slug=slug,
        owner=request.user,
        is_active=True,
    )

    if request.method != "POST":
        return redirect(
            "businesses:detail",
            slug=business.slug,
        )

    selected_ids = request.POST.getlist("media_ids")

    if not selected_ids:
        messages.warning(
            request,
            "Select at least one gallery image to delete.",
        )
        return redirect(
            "businesses:detail",
            slug=business.slug,
        )

    media_items = BusinessMedia.objects.filter(
        business=business,
        is_active=True,
        pk__in=selected_ids,
    )

    deleted_count = media_items.count()
    media_items.delete()

    messages.success(
        request,
        (
            f"{deleted_count} gallery image"
            f"{'s' if deleted_count != 1 else ''} deleted."
        ),
    )

    return redirect(
        "businesses:detail",
        slug=business.slug,
    )
