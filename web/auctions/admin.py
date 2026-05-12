from django.contrib import admin
from .models import DigitalItem, Auction, Bid, BidWallet
from .models import NodeProfile
from .models import AICompanion, AIConversation, AIMessage


@admin.register(DigitalItem)
class DigitalItemAdmin(admin.ModelAdmin):
    list_display = ("title",)


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
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
