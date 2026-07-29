from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html
from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from .admin_forms import (
    AuctionAdminForm,
    AuctionStudioImageUploadForm,
    AuctionStudioVideoUploadForm,
)
from .forms import process_fanz_image_upload
from django.utils.html import format_html
from .models import (
    AICreatorMemory,
    AICompanion,
    AIConversation,
    AIFanMemoryNote,
    AIMessage,
    Auction,
    AuctionMedia,
    Bid,
    BidWallet,
    DigitalItem,
    DiscoveryHub,
    DiscoveryHubTranslation,
    Event,
    NodeProfile,
    NotificationSound,
    UserProfile,
)

@admin.register(NotificationSound)
class NotificationSoundAdmin(admin.ModelAdmin):
    list_display = ("name", "sound_type", "active", "file")
    list_filter = ("sound_type", "active")


@admin.register(DigitalItem)
class DigitalItemAdmin(admin.ModelAdmin):
    list_display = ("title",)


class BaseAuctionMediaInlineForm(forms.ModelForm):
    expected_media_type = None

    class Meta:
        model = AuctionMedia
        fields = (
            "file",
            "is_active",
        )

    def clean_file(self):
        uploaded_file = self.cleaned_data.get("file")

        # Preserve the current file unless a replacement was uploaded.
        file_key = self.add_prefix("file")

        if file_key not in self.files:
            if self.instance and self.instance.pk:
                return self.instance.file
            return uploaded_file

        if (
            uploaded_file
            and self.expected_media_type
            == AuctionMedia.MEDIA_TYPE_IMAGE
        ):
            return process_fanz_image_upload(
                uploaded_file,
                platform_footer=True,
                max_width=1600,
                max_height=2400,
                quality=90,
            )

        return uploaded_file

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.media_type = self.expected_media_type

        if commit:
            instance.save()
            self.save_m2m()

        return instance

class AuctionImageInlineForm(BaseAuctionMediaInlineForm):
    expected_media_type = AuctionMedia.MEDIA_TYPE_IMAGE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["file"].widget.attrs.update(
            {
                "accept": (
                    "image/jpeg,"
                    "image/png,"
                    "image/webp,"
                    "image/avif,"
                    ".jpg,.jpeg,.png,.webp,.avif"
                ),
            }
        )


    def save(self, commit=True):
        instance = super().save(commit=False)

        if not instance.pk:
            highest_order = (
                AuctionMedia.objects.filter(
                    auction=instance.auction,
                    media_type=AuctionMedia.MEDIA_TYPE_IMAGE,
                )
                .order_by("-display_order")
                .values_list("display_order", flat=True)
                .first()
            )

            instance.display_order = (
                highest_order + 1
                if highest_order is not None
                else 0
            )

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class AuctionVideoInlineForm(BaseAuctionMediaInlineForm):
    expected_media_type = AuctionMedia.MEDIA_TYPE_VIDEO

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["file"].widget.attrs.update(
            {
                "accept": "video/mp4,.mp4",
            }
        )

    def clean_file(self):
        uploaded_file = super().clean_file()

        # An existing file is valid when no replacement was uploaded.
        file_key = self.add_prefix("file")

        if file_key not in self.files:
            return uploaded_file

        if not uploaded_file:
            return uploaded_file

        filename = getattr(uploaded_file, "name", "").lower()
        content_type = (
            getattr(uploaded_file, "content_type", "")
            or ""
        ).lower()

        if not filename.endswith(".mp4"):
            raise forms.ValidationError(
                "Auction video must be an MP4 file."
            )

        if content_type and content_type not in (
            "video/mp4",
            "application/mp4",
            "application/octet-stream",
        ):
            raise forms.ValidationError(
                "The uploaded file is not recognized as an MP4 video."
            )

        return uploaded_file


class AuctionMediaInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        # Avoid adding count errors when individual rows already have errors.
        if any(self.errors):
            return

        image_count = 0
        video_count = 0

        for form in self.forms:
            cleaned_data = getattr(form, "cleaned_data", None)

            if not cleaned_data:
                continue

            if cleaned_data.get("DELETE"):
                continue

            media_file = cleaned_data.get("file")

            # Ignore the empty extra inline row.
            if not media_file:
                continue

            media_type = cleaned_data.get("media_type")

            if media_type == AuctionMedia.MEDIA_TYPE_IMAGE:
                image_count += 1

            elif media_type == AuctionMedia.MEDIA_TYPE_VIDEO:
                video_count += 1

        errors = []

        if image_count > 8:
            errors.append(
                "An auction may contain a maximum of 8 images."
            )

        if video_count > 1:
            errors.append(
                "An auction may contain only 1 video."
            )

        if errors:
            raise ValidationError(errors)

class AuctionImageInline(admin.TabularInline):
    model = AuctionMedia
    form = AuctionImageInlineForm
    formset = AuctionMediaInlineFormSet
    fk_name = "auction"
    extra = 1
    max_num = 8
    verbose_name = "Auction image"
    verbose_name_plural = "Auction Images"

    fields = (
        "media_preview",
        "hero_control",
        "file",
        "is_active",
    )

    readonly_fields = (
        "media_preview",
        "hero_control",
        "current_price",
    )

    ordering = (
        "display_order",
        "created_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            media_type=AuctionMedia.MEDIA_TYPE_IMAGE,
        )

    def save_new(self, form, commit=True):
        obj = form.save(commit=False)
        obj.media_type = AuctionMedia.MEDIA_TYPE_IMAGE

        if commit:
            obj.save()

        return obj

    @admin.display(description="Preview")
    def media_preview(self, obj):
        if not obj or not obj.pk or not obj.file:
            return "Save image to preview."

        return format_html(
            '<img src="{}" style="width: 90px; height: 90px; '
            'object-fit: cover; border-radius: 8px;" />',
            obj.file.url,
        )

    @admin.display(description="Hero")
    def hero_control(self, obj):
        if not obj or not obj.pk:
            return "Save first."

        if obj.display_order == 0 and obj.is_active:
            return format_html(
                '<strong style="white-space: nowrap;">⭐ Hero</strong>'
            )

        url = reverse(
            "admin:auctions_auction_make_hero",
            args=[obj.auction_id, obj.pk],
        )

        return format_html(
            '<a class="button" href="{}">⭐ Make Hero</a>',
            url,
        )


class AuctionVideoInline(admin.TabularInline):
    model = AuctionMedia
    form = AuctionVideoInlineForm
    fk_name = "auction"
    extra = 1
    max_num = 1
    verbose_name = "Auction video"
    verbose_name_plural = "Auction Video"

    fields = (
        "media_preview",
        "file",
        "is_active",
    )

    readonly_fields = (
        "media_preview",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            media_type=AuctionMedia.MEDIA_TYPE_VIDEO,
        )

    def save_new(self, form, commit=True):
        obj = form.save(commit=False)
        obj.media_type = AuctionMedia.MEDIA_TYPE_VIDEO

        if commit:
            obj.save()

        return obj

    @admin.display(description="Preview")
    def media_preview(self, obj):
        if not obj or not obj.pk or not obj.file:
            return "Save video to preview."

        return format_html(
            '<video controls preload="metadata" '
            'style="width: 180px; max-height: 110px; border-radius: 8px;">'
            '<source src="{}" type="video/mp4">'
            "</video>",
            obj.file.url,
        )


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


@admin.register(AuctionMedia)
class AuctionMediaAdmin(admin.ModelAdmin):
    list_display = (
        "auction",
        "media_type",
        "display_order",
        "is_active",
        "created_at",
    )

    list_filter = (
        "media_type",
        "is_active",
    )

    search_fields = (
        "auction__title",
        "caption",
    )

    ordering = (
        "auction",
        "display_order",
    )

@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("auction", "user", "amount", "created_at")
    list_filter = ("auction", "user")


@admin.register(BidWallet)
class BidWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "credits")


@admin.register(NodeProfile)
class NodeProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "status", "node_name", "commission_rate")
    list_filter = ("role", "status")
    search_fields = ("user__username", "node_name")

    actions = ["approve_sales_node", "approve_validator"]

    def approve_sales_node(self, request, queryset):
        for node in queryset:
            node.role = "sales"
            node.status = "active"
            if not node.api_key:
                node.api_key = generate_api_key()
            node.save()

    def approve_validator(self, request, queryset):
        for node in queryset:
            node.role = "validator"
            node.status = "active"
            if not node.api_key:
                node.api_key = generate_api_key()
            node.save()


@admin.register(AICompanion)
class AICompanionAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "cost_per_message", "is_deluxe", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("provider", "is_deluxe", "is_active")
    search_fields = ("name",)


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ("user", "companion", "created_at", "updated_at")
    list_filter = ("companion", "created_at")


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "credits_charged", "provider_used", "created_at")
    list_filter = ("role", "provider_used", "created_at")


@admin.register(AICreatorMemory)
class AICreatorMemoryAdmin(admin.ModelAdmin):
    list_display = (
        "creator",
        "fan",
        "fan_status",
        "total_tips",
        "total_unlocks",
        "total_tip_credits",
        "total_unlock_credits",
        "conversation_count",
        "last_contact_date",
    )
    list_filter = ("fan_status", "last_contact_date")
    search_fields = ("creator__username", "fan__username")
    readonly_fields = ("first_contact_date", "last_contact_date")


@admin.register(AIFanMemoryNote)
class AIFanMemoryNoteAdmin(admin.ModelAdmin):
    list_display = (
        "creator",
        "fan",
        "note",
        "source",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "creator",
        "fan",
        "source",
        "is_active",
    )
    search_fields = (
        "creator__username",
        "fan__username",
        "note",
    )


class UserProfileInlineForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("is_ai_creator",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_ai_creator"].label = "AI Influencer badge"


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    form = UserProfileInlineForm
    can_delete = False
    extra = 0
    max_num = 1
    verbose_name = "Profile designation"
    verbose_name_plural = "Profile designation"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "display_name",
        "is_ai_creator",
        "is_ai_influencer",
    )
    list_filter = (
        "is_ai_creator",
        "is_ai_influencer",
    )
    search_fields = (
        "user__username",
        "display_name",
    )

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


@admin.register(DiscoveryHub)
class DiscoveryHubAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "hashtag",
        "is_active",
        "sort_order",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "title",
        "subtitle",
        "slug",
        "hashtag",
    )

    ordering = (
        "sort_order",
        "title",
    )

@admin.register(DiscoveryHubTranslation)
class DiscoveryHubTranslationAdmin(admin.ModelAdmin):
    list_display = (
        "hub",
        "language",
        "title",
        "template_name",
        "is_active",
    )

    list_filter = (
        "language",
        "template_name",
        "is_active",
    )

    search_fields = (
        "title",
        "subtitle",
        "hub__title",
        "hub__slug",
    )

    autocomplete_fields = ("hub",)

    fieldsets = (
        ("Hub + Language", {
            "fields": (
                "hub",
                "language",
                "is_active",
                "template_name",
            )
        }),
        ("Public Content", {
            "fields": (
                "title",
                "subtitle",
                "hero_image",
                "button_text",
                "button_url",
            )
        }),
        ("Social Sharing", {
            "fields": (
                "telegram_text",
                "pinterest_text",
            )
        }),
        ("SEO", {
            "fields": (
                "seo_title",
                "seo_description",
            )
        }),
        ("AI Experience", {
            "fields": (
                "system_prompt",
                "ai_personality",
            )
        }),
    )

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "creator",
        "business",
        "start_at",
        "end_at",
        "location",
        "is_published",
        "is_cancelled",
    )
    list_filter = (
        "is_published",
        "is_cancelled",
        "start_at",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
        "location",
        "creator__username",
        "business__name",
    )
    autocomplete_fields = (
        "creator",
        "business",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
