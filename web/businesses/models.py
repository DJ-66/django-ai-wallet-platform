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

    def __str__(self):
        return self.name
