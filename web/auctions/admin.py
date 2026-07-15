from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .forms import process_fanz_image_upload
from .models import (
    AICreatorMemory,
    AICompanion,
    AIConversation,
    AIFanMemoryNote,
    AIMessage,
    Auction,
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


class AuctionAdminForm(forms.ModelForm):
    class Meta:
        model = Auction
        fields = "__all__"

    def clean_image(self):
        image = self.cleaned_data.get("image")

        # Only process if a NEW file was uploaded in this admin save
        if "image" not in self.files:
            return self.instance.image if self.instance and self.instance.pk else image

        if image:
            return process_fanz_image_upload(
                image,
                platform_footer=True,
                max_width=1600,
                max_height=2400,
                quality=82,
            )

        return image


    def clean_image_2(self):
        image = self.cleaned_data.get("image_2")

        # Only process if a NEW file was uploaded in this admin save
        if "image_2" not in self.files:
            return self.instance.image_2 if self.instance and self.instance.pk else image

        if image:
            return process_fanz_image_upload(
                image,
                platform_footer=True,
                max_width=1600,
                max_height=2400,
                quality=82,
            )

        return image

@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    form = AuctionAdminForm
    list_display = ("title", "status", "current_price", "starts_at", "ends_at", "winner")
    list_filter = ("status",)
    search_fields = ("title",)
    fields = (
        "title",
        "digital_item",
        "status",
        "current_price",
        "starts_at",
        "ends_at",
        "image",
        "image_2",
        "video",
        "winner",
        "winner_email_sent",
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
