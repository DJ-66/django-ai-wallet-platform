from urllib.parse import urlencode
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class BusinessListing(models.Model):
    INDUSTRY_REAL_ESTATE = "real_estate"
    INDUSTRY_RESTAURANT = "restaurant"
    INDUSTRY_LAW_FIRM = "law_firm"

    INDUSTRY_CHOICES = [
        (INDUSTRY_REAL_ESTATE, _("Real Estate")),
        (INDUSTRY_RESTAURANT, _("Restaurant")),
        (INDUSTRY_LAW_FIRM, _("Law Firm")),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(
    max_length=255,
    unique=True,
    blank=True,
    )

    industry = models.CharField(
        max_length=50,
        choices=INDUSTRY_CHOICES,
    )

    description = models.TextField(blank=True)

    hero_image = models.ImageField(
        _("Business hero image"),
        upload_to="businesses/hero_images/",
        blank=True,
        null=True,
        help_text=_("Upload a wide image that represents your business."),
    )

    address = models.CharField(
        max_length=500,
        blank=True,
        help_text="Full public street address for this business.",
    )
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)

    website_url = models.URLField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_listings",
    )

    is_claimed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    source_name = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text=(
            "Name of the external source that supplied this listing."
        ),
    )

    source_url = models.URLField(
        max_length=1000,
        blank=True,
        help_text="Original public source URL for this listing.",
    )

    source_external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "Business identifier assigned by the external source."
        ),
    )

    is_imported = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_community = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "Marks this listing as a reusable community business template."
        ),
    )

    last_imported_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    discovery_hub = models.ForeignKey(
        "auctions.DiscoveryHub",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_listings",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Business Listing"
        verbose_name_plural = "Business Listings"
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "source_name",
                    "source_external_id",
                ),
                condition=(
                    models.Q(source_name__gt="")
                    & models.Q(source_external_id__gt="")
                ),
                name="unique_business_external_source",
            ),
        ]

    @property
    def google_maps_url(self):
        if self.source_url:
            return self.source_url

        location_parts = [
            self.name,
            self.address,
            self.city,
            self.country,
        ]
        query = ", ".join(
            part.strip()
            for part in location_parts
            if part and part.strip()
        )

        if not query:
            return ""

        return "https://www.google.com/maps/search/?" + urlencode(
            {
                "api": "1",
                "query": query,
            }
        )

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "business"
            candidate = base_slug
            number = 2

            while BusinessListing.objects.exclude(
                pk=self.pk
            ).filter(slug=candidate).exists():
                candidate = f"{base_slug}-{number}"
                number += 1

            self.slug = candidate

        super().save(*args, **kwargs)


    def __str__(self):
        return self.name



class BusinessFan(models.Model):
    business = models.ForeignKey(
        BusinessListing,
        on_delete=models.CASCADE,
        related_name="fans",
    )
    fan = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followed_businesses",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("business", "fan")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.fan.username} is a fan of {self.business.name}"


class BusinessUpdate(models.Model):
    business = models.ForeignKey(
        BusinessListing,
        on_delete=models.CASCADE,
        related_name="updates",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_updates",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    image = models.ImageField(
        upload_to="business_updates/",
        blank=True,
        null=True,
    )
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(
        default=False,
        help_text="Show this update at the top of the business page.",
    )

    scheduled_for = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
        help_text="When this update becomes publicly visible.",
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business.name}: {self.title}"


class BusinessMedia(models.Model):
    MEDIA_TYPE_IMAGE = "image"

    MEDIA_TYPE_CHOICES = [
        (MEDIA_TYPE_IMAGE, "Image"),
    ]

    business = models.ForeignKey(
        BusinessListing,
        on_delete=models.CASCADE,
        related_name="media",
    )

    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default=MEDIA_TYPE_IMAGE,
    )

    image = models.ImageField(
        upload_to="businesses/media/",
    )

    caption = models.CharField(
        max_length=200,
        blank=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first.",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "display_order",
            "-created_at",
        ]
        verbose_name = "Business Media"
        verbose_name_plural = "Business Media"

    def __str__(self):
        return f"{self.business.name}: {self.caption or 'Business image'}"
