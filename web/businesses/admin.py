from django.contrib import admin
from .models import BusinessListing, BusinessUpdate
from django.utils.translation import gettext_lazy as _
from .forms import BusinessListingAdminForm


@admin.register(BusinessListing)
class BusinessListingAdmin(admin.ModelAdmin):
    form = BusinessListingAdminForm
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
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "slug",
                    "industry",
                    "description",
                    "hero_image",
                ),
            },
        ),
        (
            _("Location"),
            {
                "fields": (
                    "city",
                    "country",
                    "discovery_hub",
                ),
            },
        ),
        (
            _("Contact"),
            {
                "fields": (
                    "website_url",
                    "phone",
                    "email",
                ),
            },
        ),
        (
            _("Ownership and status"),
            {
                "fields": (
                    "owner",
                    "is_claimed",
                    "is_active",
                ),
            },
        ),
        (
            _("Dates"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

@admin.register(BusinessUpdate)
class BusinessUpdateAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "business",
        "author",
        "is_published",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "is_published",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "title",
        "body",
        "business__name",
        "author__username",
    )
    autocomplete_fields = (
        "business",
        "author",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
