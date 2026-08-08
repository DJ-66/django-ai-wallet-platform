from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.translation import gettext_lazy as _

from .admin_forms import (
    DigitalItemTranslationForm,
    DiscoveryHubAdminForm,
    DiscoveryHubTranslationAdminForm,
)

from .models import (
    AICreatorMemory,
    AICompanion,
    AIConversation,
    AIFanMemoryNote,
    AIMessage,
    Bid,
    BidWallet,
    DigitalItem,
    DigitalItemTranslation,
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
    list_display = (
        "title",
        "translate_link",
    )

    change_form_template = (
        "admin/auctions/digitalitem/change_form.html"
    )

    @admin.display(description=_("Translations"))
    def translate_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse

        url = reverse(
            "admin:auctions_digitalitem_translate",
            args=[obj.pk],
        )

        return format_html(
            '<a href="{}">{}</a>',
            url,
            _("Translate / Localize"),
        )

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "<int:item_id>/translate/",
                self.admin_site.admin_view(
                    self.translate_view
                ),
                name="auctions_digitalitem_translate",
            ),
        ]

        return custom_urls + urls

    def translate_view(self, request, item_id):
        item = get_object_or_404(
            DigitalItem,
            pk=item_id,
        )

        if not self.has_change_permission(request, item):
            self.message_user(
                request,
                _("You do not have permission to modify this digital item."),
                level="error",
            )
            return redirect(
                "admin:auctions_digitalitem_changelist"
            )

        language_choices = (
            DigitalItemTranslation.LANGUAGE_CHOICES
        )

        forms_by_language = []

        for language_code, language_name in language_choices:
            translation = (
                DigitalItemTranslation.objects
                .filter(
                    digital_item=item,
                    language=language_code,
                )
                .first()
            )

            form = DigitalItemTranslationForm(
                request.POST or None,
                request.FILES or None,
                instance=translation,
                prefix=language_code,
            )

            forms_by_language.append(
                (
                    language_code,
                    language_name,
                    form,
                    translation,
                )
            )

        if request.method == "POST":
            all_valid = all(
                form.is_valid()
                for _, _, form, _ in forms_by_language
            )

            if all_valid:
                for (
                    language_code,
                    _language_name,
                    form,
                    translation,
                ) in forms_by_language:

                    has_content = any(
                        [
                            form.cleaned_data.get("title"),
                            form.cleaned_data.get("description"),
                            form.cleaned_data.get("file"),
                            form.cleaned_data.get("delivery_url"),
                        ]
                    )

                    if translation or has_content:
                        obj = form.save(commit=False)

                        obj.digital_item = item
                        obj.language = language_code
                        obj.save()

                self.message_user(
                    request,
                    _("Digital item translations saved."),
                    level="success",
                )

                return redirect(
                    "admin:auctions_digitalitem_translate",
                    item_id=item.pk,
                )

        context = {
            **self.admin_site.each_context(request),
            "title": _("Translate Digital Item"),
            "original": item,
            "item": item,
            "forms_by_language": forms_by_language,
            "opts": self.model._meta,
        }

        return TemplateResponse(
            request,
            "admin/auctions/digitalitem/translate.html",
            context,
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
                node.api_key = NodeProfile.generate_api_key()
            node.save()

    def approve_validator(self, request, queryset):
        for node in queryset:
            node.role = "validator"
            node.status = "active"
            if not node.api_key:
                node.api_key = NodeProfile.generate_api_key()
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
    form = DiscoveryHubAdminForm

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
    form = DiscoveryHubTranslationAdminForm

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
