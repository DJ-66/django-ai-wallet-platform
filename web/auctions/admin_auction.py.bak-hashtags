from .hashtags import sync_auction_hashtags
from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html

from .admin_forms import (
    AuctionAdminForm,
    AuctionStudioImageUploadForm,
    AuctionStudioVideoUploadForm,
)
from .forms import process_fanz_image_upload
from .models import Auction, AuctionMedia


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    form = AuctionAdminForm

    change_form_template = (
        "admin/auctions/auction/change_form.html"
    )

    list_display = (
        "hero_thumbnail",
        "title",
        "status",
        "current_price",
        "starts_at",
        "ends_at",
        "winner",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "title",
        "digital_item__title",
    )

    ordering = (
        "-created_at",
    )

    def save_model(self, request, obj, form, change):
        if not change:
            # A new auction always opens at its configured starting price.
            obj.current_price = obj.starting_price

        elif (
            "starting_price" in form.changed_data
            and not obj.bids.exists()
        ):
            # Before bidding begins, changing the starting price also changes
            # the current price.
            obj.current_price = obj.starting_price

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    def save_related(self, request, form, formsets, change):
        """
        Save admin many-to-many relationships first, then derive the
        auction's Discovery hashtags from its title.
        """
        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        sync_auction_hashtags(form.instance)

    def response_add(self, request, obj, post_url_continue=None):
        self.message_user(
            request,
            "Auction created. Add images and video in FANZ Auction Studio.",
            level="success",
        )

        return redirect(
            "admin:auctions_auction_change",
            obj.pk,
        )

    @admin.display(description="Hero")
    def hero_thumbnail(self, obj):
        hero = obj.hero_media()

        if not hero or not hero.file:
            return "—"

        try:
            return format_html(
                '<img src="{}" alt="Auction hero" '
                'style="width:64px;height:64px;'
                'object-fit:cover;border-radius:8px;" />',
                hero.file.url,
            )
        except ValueError:
            return "—"


    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "<int:auction_id>/make-hero/<int:media_id>/",
                self.admin_site.admin_view(
                    self.make_hero_view
                ),
                name="auctions_auction_make_hero",
            ),
            path(
                "<int:auction_id>/upload-images/",
                self.admin_site.admin_view(
                    self.upload_images_view
                ),
                name="auctions_auction_upload_images",
            ),

            path(
                "<int:auction_id>/upload-video/",
                self.admin_site.admin_view(
                    self.upload_video_view
            ),
            name="auctions_auction_upload_video",
        ),

        path(
            "<int:auction_id>/delete-image/<int:media_id>/",
            self.admin_site.admin_view(
                self.delete_image_view
            ),
            name="auctions_auction_delete_image",
        ),
        path(
            "<int:auction_id>/delete-video/<int:media_id>/",
            self.admin_site.admin_view(
                self.delete_video_view
            ),
            name="auctions_auction_delete_video",
        ),


        ]

        return custom_urls + urls

    def make_hero_view(self, request, auction_id, media_id):
        auction = get_object_or_404(
            Auction,
            pk=auction_id,
        )

        if not self.has_change_permission(request, auction):
            self.message_user(
                request,
                "You do not have permission to modify this auction.",
                level="error",
            )
            return redirect(
                "admin:auctions_auction_changelist"
            )

        media = get_object_or_404(
            AuctionMedia,
            pk=media_id,
            auction=auction,
        )

        if media.media_type != AuctionMedia.MEDIA_TYPE_IMAGE:
            self.message_user(
                request,
                "Only auction images can become the hero.",
                level="error",
            )
        else:
            media.make_hero()

            self.message_user(
                request,
                "The selected image is now the auction hero.",
                level="success",
            )

        return redirect(
            "admin:auctions_auction_change",
            auction.pk,
        )

    def upload_images_view(self, request, auction_id):
        auction = get_object_or_404(
            Auction,
            pk=auction_id,
        )

        if not self.has_change_permission(request, auction):
            self.message_user(
                request,
                "You do not have permission to modify this auction.",
                level="error",
            )
            return redirect(
                "admin:auctions_auction_changelist"
            )

        if request.method == "GET":
            form = AuctionStudioImageUploadForm()

            context = {
                **self.admin_site.each_context(request),
                "title": f"Upload images: {auction.title}",
                "auction": auction,
                "form": form,
                "opts": self.model._meta,
            }

            return TemplateResponse(
                request,
                "admin/auctions/auction/upload_images.html",
                context,
            )

        form = AuctionStudioImageUploadForm(
            request.POST,
            request.FILES,
        )

        if not form.is_valid():
            context = {
                **self.admin_site.each_context(request),
                "title": f"Upload images: {auction.title}",
                "auction": auction,
                "form": form,
                "opts": self.model._meta,
            }

            return TemplateResponse(
                request,
                "admin/auctions/auction/upload_images.html",
                context,
            )

        uploaded_images = form.cleaned_data["images"]

        existing_count = auction.media.filter(
            media_type=AuctionMedia.MEDIA_TYPE_IMAGE,
        ).count()

        available_slots = 8 - existing_count

        if len(uploaded_images) > available_slots:
            self.message_user(
                request,
                (
                    f"This auction has room for only "
                    f"{available_slots} more image(s)."
                ),
                level="error",
            )
            return redirect(
                "admin:auctions_auction_upload_images",
                auction.pk,
            )

        next_order = (
            auction.media.filter(
                media_type=AuctionMedia.MEDIA_TYPE_IMAGE,
            )
            .order_by("-display_order")
            .values_list("display_order", flat=True)
            .first()
        )

        next_order = (
            next_order + 1
            if next_order is not None
            else 0
        )

        for uploaded_image in uploaded_images:
            processed_image = process_fanz_image_upload(
                uploaded_image,
                platform_footer=True,
                max_width=1600,
                max_height=2400,
                quality=90,
            )

            AuctionMedia.objects.create(
                auction=auction,
                file=processed_image,
                media_type=AuctionMedia.MEDIA_TYPE_IMAGE,
                display_order=next_order,
                is_active=True,
            )

            next_order += 1

        self.message_user(
            request,
            f"{len(uploaded_images)} auction image(s) uploaded.",
            level="success",
        )

        return redirect(
            "admin:auctions_auction_change",
            auction.pk,
        )

    def upload_video_view(self, request, auction_id):
        auction = get_object_or_404(
            Auction,
            pk=auction_id,
        )

        if not self.has_change_permission(request, auction):
            self.message_user(
                request,
                "You do not have permission to modify this auction.",
                level="error",
            )
            return redirect(
                "admin:auctions_auction_changelist"
            )

        if request.method == "GET":
            form = AuctionStudioVideoUploadForm()

            context = {
                **self.admin_site.each_context(request),
                "title": f"Upload video: {auction.title}",
                "auction": auction,
                "form": form,
                "opts": self.model._meta,
            }

            return TemplateResponse(
                request,
                "admin/auctions/auction/upload_video.html",
                context,
            )

        form = AuctionStudioVideoUploadForm(
            request.POST,
            request.FILES,
        )

        if not form.is_valid():
            context = {
                **self.admin_site.each_context(request),
                "title": f"Upload video: {auction.title}",
                "auction": auction,
                "form": form,
                "opts": self.model._meta,
            }

            return TemplateResponse(
                request,
                "admin/auctions/auction/upload_video.html",
                context,
            )

        uploaded_video = form.cleaned_data["video"]

        existing_video = auction.media.filter(
            media_type=AuctionMedia.MEDIA_TYPE_VIDEO,
        ).first()

        if existing_video:
            self.message_user(
                request,
                "This auction already has a video. Replace or delete it first.",
                level="error",
            )
            return redirect(
                "admin:auctions_auction_change",
                auction.pk,
            )

        AuctionMedia.objects.create(
            auction=auction,
            file=uploaded_video,
            media_type=AuctionMedia.MEDIA_TYPE_VIDEO,
            display_order=0,
            is_active=True,
        )

        self.message_user(
            request,
            "Auction video uploaded.",
            level="success",
        )

        return redirect(
            "admin:auctions_auction_change",
            auction.pk,
        )

    def delete_image_view(self, request, auction_id, media_id):
        auction = get_object_or_404(
            Auction,
            pk=auction_id,
        )

        if not self.has_change_permission(request, auction):
            self.message_user(
                request,
                "You do not have permission to modify this auction.",
                level="error",
            )
            return redirect(
                "admin:auctions_auction_changelist"
            )

        media = get_object_or_404(
            AuctionMedia,
            pk=media_id,
            auction=auction,
            media_type=AuctionMedia.MEDIA_TYPE_IMAGE,
        )

        if request.method != "POST":
            self.message_user(
                request,
                "Image deletion must be submitted from Auction Studio.",
                level="error",
            )
            return redirect(
                "admin:auctions_auction_change",
                auction.pk,
            )

        media_file = media.file
        media.delete()

        if media_file:
            media_file.delete(save=False)

        remaining_images = list(
            auction.media.filter(
                media_type=AuctionMedia.MEDIA_TYPE_IMAGE,
            ).order_by(
                "display_order",
                "created_at",
            )
        )

        for index, image in enumerate(remaining_images):
            if image.display_order != index:
                image.display_order = index
                image.save(update_fields=["display_order"])

        self.message_user(
            request,
            "Auction image deleted.",
            level="success",
        )

        return redirect(
            "admin:auctions_auction_change",
            auction.pk,
        )

    def delete_video_view(self, request, auction_id, media_id):
        auction = get_object_or_404(
            Auction,
            pk=auction_id,
        )

        if not self.has_change_permission(request, auction):
            self.message_user(
                request,
                "You do not have permission to modify this auction.",
                level="error",
            )
            return redirect(
                "admin:auctions_auction_changelist"
            )

        media = get_object_or_404(
            AuctionMedia,
            pk=media_id,
            auction=auction,
            media_type=AuctionMedia.MEDIA_TYPE_VIDEO,
        )

        if request.method != "POST":
            self.message_user(
                request,
                "Video deletion must be submitted from Auction Studio.",
                level="error",
            )
            return redirect(
                "admin:auctions_auction_change",
                auction.pk,
            )

        media_file = media.file
        media.delete()

        if media_file:
            media_file.delete(save=False)

        self.message_user(
            request,
            "Auction video deleted.",
            level="success",
        )

        return redirect(
            "admin:auctions_auction_change",
            auction.pk,
        )
