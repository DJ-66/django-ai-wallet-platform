from django.contrib import admin

from .models import AuctionMedia


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
