from django.contrib import admin

from .models import BusinessListing


@admin.register(BusinessListing)
class BusinessListingAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "industry",
        "city",
        "country",
        "is_claimed",
        "is_active",
        "created_at",
    )
    list_filter = (
        "industry",
        "is_claimed",
        "is_active",
        "country",
        "city",
    )
    search_fields = (
        "name",
        "description",
        "city",
        "country",
        "email",
        "phone",
    )
    prepopulated_fields = {
        "slug": ("name",),
    }
    autocomplete_fields = (
        "owner",
        "discovery_hub",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
