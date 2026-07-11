from urllib.parse import urlencode
from django.conf import settings
from django.db import models

class BusinessListing(models.Model):
    INDUSTRY_REAL_ESTATE = "real_estate"
    INDUSTRY_RESTAURANT = "restaurant"
    INDUSTRY_LAW_FIRM = "law_firm"

    INDUSTRY_CHOICES = [
        (INDUSTRY_REAL_ESTATE, "Real Estate"),
        (INDUSTRY_RESTAURANT, "Restaurant"),
        (INDUSTRY_LAW_FIRM, "Law Firm"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    industry = models.CharField(
        max_length=50,
        choices=INDUSTRY_CHOICES,
    )

    description = models.TextField(blank=True)

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

    @property
    def google_maps_url(self):
        location_parts = [
            self.name,
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

    @property
    def google_maps_url(self):
        location_parts = [
            self.name,
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business.name}: {self.title}"
