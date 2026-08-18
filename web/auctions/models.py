import uuid
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils.text import slugify
from django.db import transaction, models
from django.core.exceptions import ValidationError

from .validators import (
    FOUNDER_FLOOR_CREDITS,
    normalize_founder_handle,
    validate_founder_handle,
)

class NotificationSound(models.Model):
    SOUND_TYPES = [
        ("cash", "Cash / Ka-ching"),
        ("social", "Social / Tink"),
    ]

    name = models.CharField(max_length=80)
    sound_type = models.CharField(max_length=20, choices=SOUND_TYPES)
    file = models.FileField(upload_to="notification_sounds/")
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.sound_type})"


class DigitalItem(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="digital_items/", blank=True, null=True)
    delivery_url = models.URLField(blank=True)

    def __str__(self):
        return self.title

class DigitalItemTranslation(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("es", "Spanish"),
        ("pt", "Portuguese"),
    ]

    digital_item = models.ForeignKey(
        DigitalItem,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
    )

    title = models.CharField(
        max_length=200,
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    file = models.FileField(
        upload_to="digital_item_translations/",
        blank=True,
        null=True,
    )

    delivery_url = models.URLField(
        blank=True,
    )

    class Meta:
        unique_together = (
            "digital_item",
            "language",
        )
        ordering = [
            "digital_item_id",
            "language",
        ]

    def __str__(self):
        return f"{self.digital_item.title} ({self.language})"


class Auction(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("live", "Live"),
        ("ended", "Ended"),
    ]

    title = models.CharField(max_length=200)
    digital_item = models.ForeignKey(DigitalItem, on_delete=models.PROTECT)
    hashtags = models.ManyToManyField("Hashtag", related_name="auctions", blank=True,)
    video = models.FileField(upload_to="auction_videos/", blank=True, null=True)
    image = models.ImageField(upload_to="auction_images/", blank=True, null=True)
    image_2 = models.ImageField(upload_to="auction_images/", blank=True, null=True)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bid_increment = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    starting_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    reminder_60_sent = models.BooleanField(default=False)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    winner_email_sent = models.BooleanField(default=False)

    def is_live(self):
        now = timezone.now()
        return self.status == "live" and self.starts_at <= now < self.ends_at

    def active_images(self):
        return self.media.filter(
            media_type="image",
            is_active=True,
        ).order_by(
            "display_order",
            "created_at",
        )

    def hero_media(self):
        return self.active_images().first()

    def gallery_media(self):
        return self.active_images()[1:]

    def active_video(self):
        return self.media.filter(
            media_type="video",
            is_active=True,
        ).order_by(
            "display_order",
            "created_at",
        ).first()


    def __str__(self):
        return self.title

class AuctionTranslation(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("es", "Spanish"),
        ("pt", "Portuguese"),
    ]

    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
    )

    title = models.CharField(
        max_length=200,
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    hero_image = models.ImageField(
        upload_to="auction_translations/",
        blank=True,
        null=True,
    )

    use_language_hero = models.BooleanField(
        default=False,
    )

    class Meta:
        unique_together = (
            "auction",
            "language",
        )
        ordering = [
            "auction_id",
            "language",
        ]

    def __str__(self):
        return f"{self.auction.title} ({self.language})"

class AuctionMedia(models.Model):
    MEDIA_TYPE_IMAGE = "image"
    MEDIA_TYPE_VIDEO = "video"

    MEDIA_TYPE_CHOICES = [
        (MEDIA_TYPE_IMAGE, "Image"),
        (MEDIA_TYPE_VIDEO, "Video"),
    ]

    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name="media",
    )

    file = models.FileField(
        upload_to="auctions/media/",
    )

    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default=MEDIA_TYPE_IMAGE,
        db_index=True,
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
            "created_at",
        ]
        verbose_name = "Auction Media"
        verbose_name_plural = "Auction Media"

    def make_hero(self):
        if self.media_type != self.MEDIA_TYPE_IMAGE:
            raise ValueError("Only auction images can become the hero.")

        with transaction.atomic():
            ordered_images = list(
                AuctionMedia.objects.select_for_update()
                .filter(
                    auction=self.auction,
                    media_type=self.MEDIA_TYPE_IMAGE,
                    is_active=True,
                )
                .order_by(
                    "display_order",
                    "created_at",
                    "pk",
                )
            )

            ordered_images = [
                media
                for media in ordered_images
                if media.pk != self.pk
            ]

            if not self.is_active:
                self.is_active = True

            self.display_order = 0
            self.save(
                update_fields=[
                    "display_order",
                    "is_active",
                    "updated_at",
                ]
            )

            for position, media in enumerate(
                ordered_images,
                start=1,
            ):
                if media.display_order != position:
                    AuctionMedia.objects.filter(
                        pk=media.pk,
                    ).update(
                        display_order=position,
                    )


    def __str__(self):
        return (
            f"Auction {self.auction_id}: "
            f"{self.get_media_type_display()} "
            f"#{self.display_order + 1}"
        )


class Bid(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="bids")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


class BidWallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    credits = models.PositiveIntegerField(default=0)

    pay_code = models.CharField(max_length=12, unique=True, blank=True, null=True)
    wallet_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    signup_bonus_given = models.BooleanField(default=False)

    referral_code = models.CharField(max_length=12, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referred_users"
    )

    pending_referral_business = models.ForeignKey(
        "businesses.BusinessListing",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pending_referral_wallets",
    )

    referral_bonus_given = models.BooleanField(default=False)

    source_node = models.ForeignKey(
        "NodeProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referred_wallets"
)

    def __str__(self):
        return f"{self.user} ({self.credits} credits)"

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("transfer", "Transfer"),
        ("tip", "Tip"),
        ("unlock", "Premium Unlock"),
        ("purchase", "Purchase"),
        ("commission", "Commission"),
        ("bonus", "Bonus"),
        ("game", "Game"),
        ("ai_message", "AI Message"),
]

    sender = models.ForeignKey(
        "BidWallet",
        null=True,
        blank=True,
        related_name="sent_transactions",
        on_delete=models.SET_NULL
    )

    receiver = models.ForeignKey(
        "BidWallet",
        null=True,
        blank=True,
        related_name="received_transactions",
        on_delete=models.SET_NULL
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES
    )

    reference = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} → {self.receiver} ({self.amount})"


class NodeProfile(models.Model):
    ROLE_CHOICES = [
        ("affiliate", "Affiliate Host"),
        ("sales", "Sales Node Operator"),
        ("validator", "Validator Node Operator"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("suspended", "Suspended"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="affiliate")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    node_name = models.CharField(max_length=120, blank=True)
    node_slug = models.SlugField(max_length=80, unique=True, blank=True, null=True)
    node_domain = models.CharField(max_length=255, blank=True)

    api_key = models.CharField(max_length=64, unique=True, blank=True, null=True)
    validator_public_key = models.TextField(blank=True)

    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)

    def is_affiliate(self):
        return self.role == "affiliate"

    def can_sell_credits(self):
        return self.role in ["sales", "validator"] and self.status == "active"

    def can_validate(self):
        return self.role == "validator" and self.status == "active"

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def generate_api_key():
        return secrets.token_urlsafe(32)


class CreditPackage(models.Model):
    name = models.CharField(max_length=100)

    credits = models.PositiveIntegerField(
        help_text="Number of credits the user receives"
    )

    price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in USD (used for commission calculations)"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.credits} credits (${self.price_usd})"


class CreditPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet = models.ForeignKey("BidWallet", on_delete=models.CASCADE)

    package = models.ForeignKey("CreditPackage", on_delete=models.PROTECT)

    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)

    external_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Idempotency key (Stripe payment ID, crypto tx hash, etc)"
    )

    source_type = models.CharField(
        max_length=20,
        choices=[
            ("direct", "Direct"),
            ("referral", "Referral"),
            ("node", "Node"),
        ],
        default="direct"
    )

    source_node = models.ForeignKey(
        "NodeProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.package} - ${self.amount_paid}"

EVENT_TYPES = [
    ("general", "General"),
    ("promotion", "Promotion"),
    ("music", "Live Music"),
    ("food", "Food"),
    ("community", "Community"),
    ("private", "Private"),
    ("holiday", "Holiday"),
]


class Event(models.Model):
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_events",
    )
    business = models.ForeignKey(
        "businesses.BusinessListing",
        on_delete=models.SET_NULL,
        related_name="events",
        blank=True,
        null=True,
    )
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        default="general",
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    location = models.CharField(
        max_length=255,
        blank=True,
    )
    image = models.ImageField(
        upload_to="events/",
        blank=True,
        null=True,
    )
    is_published = models.BooleanField(default=True)
    is_cancelled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at"]

    def __str__(self):
        return self.title


class AICompanion(models.Model):
    PROVIDER_CHOICES = [
        ("local_ollama", "Local Ollama"),
        ("local_deepseek", "Local DeepSeek"),
        ("openai", "OpenAI Deluxe"),
    ]

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_companions",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default="local_deepseek")

    prompt_key = models.CharField(
        max_length=50,
        default="flirty_social",
    )

    system_prompt = models.TextField()
    cost_per_message = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_deluxe = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return self.name


class AIConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    companion = models.ForeignKey("AICompanion", on_delete=models.CASCADE)
    is_pinned = models.BooleanField(default=False)
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} → {self.companion.name}"


class AIMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    conversation = models.ForeignKey(
        "AIConversation",
        on_delete=models.CASCADE,
        related_name="messages"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    credits_charged = models.PositiveIntegerField(default=0)
    provider_used = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"


class AICreatorMemory(models.Model):
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_creator_memories"
    )
    fan = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_fan_memories"
    )

    fan_status = models.BooleanField(default=False)

    total_tips = models.PositiveIntegerField(default=0)
    total_unlocks = models.PositiveIntegerField(default=0)
    total_tip_credits = models.PositiveIntegerField(default=0)
    total_unlock_credits = models.PositiveIntegerField(default=0)

    first_contact_date = models.DateTimeField(auto_now_add=True)
    last_contact_date = models.DateTimeField(auto_now=True)

    conversation_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("creator", "fan")
        ordering = ["-last_contact_date"]

    def __str__(self):
        return f"{self.fan.username} → {self.creator.username}"

    @property
    def relationship_score(self):
        score = 0
        score += self.total_tips * 3
        score += self.total_unlocks * 5
        score += self.conversation_count

        if self.fan_status:
            score += 10

        return score

    @property
    def relationship_tier(self):
        score = self.relationship_score

        if score >= 100:
            return "Super Fan"
        if score >= 50:
            return "VIP"
        if score >= 25:
            return "Supporter"
        if score >= 10:
            return "Fan"

        return "Visitor"

class AIFanMemoryNote(models.Model):
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_fan_memory_notes_created",
    )

    fan = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_fan_memory_notes",
    )

    note = models.CharField(max_length=255)

    source = models.CharField(
        max_length=50,
        blank=True,
        default="manual",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.creator} remembers {self.fan}: {self.note}"


class FavoriteAuction(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="favorite_auctions",
    )
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "auction")

class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    display_name = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)
    is_ai_creator = models.BooleanField(default=False)

    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True
    )

    is_ai_influencer = models.BooleanField(
        default=False,
        help_text="Display the AI Influencer badge on the public profile."
    )

    
    banner = models.ImageField(
        upload_to="profile_banners/",
        blank=True,
        null=True
    )


    bank_qr_image = models.ImageField(
        upload_to="payment_qr/",
        blank=True,
        null=True
    )

    bank_payment_notes = models.TextField(
        blank=True
    )
    
    location = models.CharField(max_length=120, blank=True)

    website = models.URLField(blank=True)
    youtube = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    x_url = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)
    telegram = models.URLField(blank=True)
    whatsapp = models.CharField(max_length=40, blank=True)

    featured_link_1_label = models.CharField(max_length=80, blank=True)
    featured_link_1_url = models.URLField(blank=True)

    featured_link_2_label = models.CharField(max_length=80, blank=True)
    featured_link_2_url = models.URLField(blank=True)

    featured_link_3_label = models.CharField(max_length=80, blank=True)
    featured_link_3_url = models.URLField(blank=True) 


    fan_count = models.PositiveIntegerField(default=0)

    is_verified = models.BooleanField(default=False)
    is_official = models.BooleanField(default=False)
    is_platform_account = models.BooleanField(
        default=False,
        help_text="FANZ Platform Account.",
    )
    is_ai_creator = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.display_name or self.user.username


class UserProfileTranslation(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("es", "Spanish"),
        ("pt", "Portuguese"),
    ]

    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
    )

    bio = models.TextField(
        blank=True,
    )

    bank_payment_notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "language"],
                name="unique_user_profile_translation_language",
            ),
        ]

    def __str__(self):
        return f"{self.profile} [{self.language}]"

class Hashtag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    usage_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"#{self.name}"

class FeedPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    title = models.CharField(
        max_length=120,
        blank=True,
        default=""
    )

    content = models.TextField(max_length=2000)

    hashtags = models.ManyToManyField(
        "Hashtag",
        blank=True,
        related_name="posts"
    )

    image = models.ImageField(
        upload_to="feed/",
        blank=True,
        null=True
    )
    
    is_pinned = models.BooleanField(default=False)

    is_public = models.BooleanField(default=True)

    # 🔒 Paid / locked posts
    is_paid = models.BooleanField(default=False)

    unlock_price = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.content[:40]}"


class FeedPostTranslation(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("es", "Spanish"),
        ("pt", "Portuguese"),
    ]

    post = models.ForeignKey(
        FeedPost,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
    )

    title = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    content = models.TextField(
        max_length=2000,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "language"],
                name="unique_feed_post_translation_language",
            ),
        ]

    def __str__(self):
        return f"{self.post_id} [{self.language}]"

class FeedPostMedia(models.Model):
    MEDIA_TYPE_IMAGE = "image"
    MEDIA_TYPE_VIDEO = "video"
    MEDIA_TYPE_AUDIO = "audio"
    MEDIA_TYPE_PDF = "pdf"

    MEDIA_TYPE_CHOICES = [
        (MEDIA_TYPE_IMAGE, "Image"),
        (MEDIA_TYPE_VIDEO, "Video"),
        (MEDIA_TYPE_AUDIO, "Audio"),
        (MEDIA_TYPE_PDF, "PDF"),
    ]

    post = models.ForeignKey(
        FeedPost,
        on_delete=models.CASCADE,
        related_name="media",
    )

    file = models.FileField(
        upload_to="feed/media/",
    )

    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default=MEDIA_TYPE_IMAGE,
        db_index=True,
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
            "created_at",
        ]
        verbose_name = "Feed Post Media"
        verbose_name_plural = "Feed Post Media"

    def __str__(self):
        return (
            f"Post {self.post_id}: "
            f"{self.caption or self.get_media_type_display()}"
        )

class PostUnlock(models.Model):
    post = models.ForeignKey(
        FeedPost,
        on_delete=models.CASCADE,
        related_name="unlocks"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    price_paid = models.PositiveIntegerField()
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")

    def __str__(self):
        return f"{self.user.username} unlocked post {self.post_id}"

class PostLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)


    post = models.ForeignKey(
        FeedPost,
        on_delete=models.CASCADE,
        related_name="likes"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")

    def __str__(self):
        return f"{self.user.username} likes {self.post.id}"

class PostComment(models.Model):
    post = models.ForeignKey(
        FeedPost,
        on_delete=models.CASCADE,
        related_name="comments"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="replies"
    )
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user.username} on post {self.post_id}"


class Fan(models.Model):
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="fans"
    )
    fan = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="fanning"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("creator", "fan")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.fan.username} is a fan of {self.creator.username}"


class Notification(models.Model):

    FAN = "fan"
    TIP = "tip"
    UNLOCK = "unlock"
    AUCTION = "auction"
    LIKE = "like"
    COMMENT = "comment"
    MESSAGE = "message"

    TYPE_CHOICES = [
        (FAN, "Fan"),
        (TIP, "Tip"),
        (UNLOCK, "Unlock"),
        (AUCTION, "Auction"),
        (LIKE, "Like"),
        (COMMENT, "Comment"),
        (MESSAGE, "Message"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notification_actions"
    )
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=FAN,
    )
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    count = models.PositiveIntegerField(default=1)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-created_at"]

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"


class Conversation(models.Model):
    participants = models.ManyToManyField(
        User,
        related_name="conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Conversation {self.id}"


class DirectMessage(models.Model):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"

    MESSAGE_TYPE_CHOICES = [
        (HUMAN, "Human"),
        (AI, "AI"),
        (SYSTEM, "System"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_direct_messages"
    )
    body = models.TextField(max_length=2000)
    original_language = models.CharField(
        max_length=5,
        blank=True,
        default="",
    )
    translations = models.JSONField(
        default=dict,
        blank=True,
    )
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default=HUMAN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    generated_by_ai = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender.username} in conversation {self.conversation_id}"



class DiscoveryHub(models.Model):
    hashtag = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    title = models.CharField(max_length=160)
    subtitle = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to="discovery_hubs/", blank=True, null=True)
    button_text = models.CharField(max_length=80, blank=True)
    button_url = models.URLField(blank=True)
    telegram_text = models.TextField(blank=True)
    pinterest_text = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.hashtag)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["sort_order", "title"]

    def get_translation(self, language="en"):
        """
        Return the best available translation for this hub.

        Fallback order:
            requested language
            Spanish (for Guaraní)
            English
        """

        fallback_order = [language]

        if language == "gn":
            fallback_order.append("es")

        if "en" not in fallback_order:
            fallback_order.append("en")

        for code in fallback_order:
            translation = (
                self.translations
                .filter(language=code, is_active=True)
                .first()
            )

            if translation:
                return translation

        return None

    def __str__(self):
        return self.title


class DiscoveryHubTranslation(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("es", "Spanish"),
        ("pt", "Portuguese"),
    ]

    hub = models.ForeignKey(
        DiscoveryHub,
        on_delete=models.CASCADE,
        related_name="translations"
    )

    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES
    )

    title = models.CharField(max_length=200)
    subtitle = models.TextField(blank=True)

    hero_image = models.ImageField(
        upload_to="discovery_hubs/",
        blank=True,
        null=True
    )

    button_text = models.CharField(max_length=100, blank=True)
    button_url = models.CharField(max_length=255, blank=True)

    telegram_text = models.TextField(blank=True)
    pinterest_text = models.TextField(blank=True)

    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.TextField(blank=True)

    template_name = models.CharField(
        max_length=100,
        blank=True,
        default="default",
        help_text="Template key for this localized Discovery Experience, e.g. default, restaurants, hotels, doctors."
    )
    
    system_prompt = models.TextField(blank=True)
    ai_personality = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("hub", "language")
        ordering = ["hub__sort_order", "language"]

    def __str__(self):
        return f"{self.hub.title} ({self.language})"

class FounderAccount(models.Model):
    """
    Permanent scarce FANZ Founder property representing one valid
    canonical 1-4 character handle.

    The property exists independently of whether a Django User
    currently occupies/operates it.
    """

    STATUS_AVAILABLE = "available"
    STATUS_OWNED = "owned"
    STATUS_LISTED = "listed"
    STATUS_RESERVED = "reserved"
    STATUS_TREASURY = "treasury"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_OWNED, "Owned"),
        (STATUS_LISTED, "Listed"),
        (STATUS_RESERVED, "Reserved"),
        (STATUS_TREASURY, "FANZ Treasury"),
    ]

    handle = models.CharField(
        max_length=4,
        unique=True,
    )

    handle_length = models.PositiveSmallIntegerField(
        blank=True,
    )

    current_account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="founder_account",
    )
    owner_root = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_founder_accounts",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_AVAILABLE,
    )

    floor_price_credits = models.PositiveIntegerField(
        default=FOUNDER_FLOOR_CREDITS,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["handle_length", "handle"]

    def clean(self):
        super().clean()

        self.handle = validate_founder_handle(self.handle)
        self.handle_length = len(self.handle)

        if self.floor_price_credits < FOUNDER_FLOOR_CREDITS:
            raise ValidationError(
                f"Founder Accounts cannot have a floor price below "
                f"{FOUNDER_FLOOR_CREDITS} credits."
            )


    def save(self, *args, **kwargs):
        self.handle = normalize_founder_handle(self.handle)
        self.handle_length = len(self.handle)

        validate_founder_handle(self.handle)

        if self.floor_price_credits < FOUNDER_FLOOR_CREDITS:
            raise ValueError(
                f"Founder Accounts cannot have a floor price below "
                f"{FOUNDER_FLOOR_CREDITS} credits."
            )

        super().save(*args, **kwargs)


    def __str__(self):
        return f"@{self.handle} (Founder)"


class AccountControl(models.Model):
    """
    Authoritative FANZ account-control edge.

    A controlled account may have at most one direct controller.
    Root accounts have no AccountControl row as controlled_account.

    Cycle prevention and authoritative-root resolution belong in the
    Founder ownership service layer, not recursive User model fields.
    """

    controller_account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="controlled_account_edges",
    )

    controlled_account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="controller_edge",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(
                    controller_account=models.F("controlled_account")
                ),
                name="account_control_no_direct_self_control",
            ),
        ]

    def __str__(self):
        return (
            f"@{self.controller_account.username} controls "
            f"@{self.controlled_account.username}"
        )

class FounderOwnershipLedger(models.Model):
    """
    Append-only authoritative ownership provenance for Founder property.

    Records are hash-chained globally in sequence order.
    Creation must go through the Founder ledger service.
    """

    TRANSFER_P2P_FIXED = "p2p_fixed"
    TRANSFER_P2P_BLIND = "p2p_blind"
    TRANSFER_MINIMUM_CONVEYANCE = "minimum_conveyance"
    TRANSFER_TREASURY_RELEASE = "treasury_release"
    TRANSFER_CB_REDEMPTION = "cb_redemption"

    TRANSFER_TYPE_CHOICES = [
        (TRANSFER_P2P_FIXED, "P2P Fixed Price"),
        (TRANSFER_P2P_BLIND, "P2P Blind Sale"),
        (
            TRANSFER_MINIMUM_CONVEYANCE,
            "Minimum Founder Conveyance",
        ),
        (
            TRANSFER_TREASURY_RELEASE,
            "FANZ Treasury Release",
        ),
        (
            TRANSFER_CB_REDEMPTION,
            "FANZ CB Redemption",
        ),
    ]

    sequence = models.PositiveBigIntegerField(
        unique=True,
        editable=False,
    )

    founder_account = models.ForeignKey(
        FounderAccount,
        on_delete=models.PROTECT,
        related_name="ownership_ledger",
    )

    handle_snapshot = models.CharField(
        max_length=4,
        editable=False,
    )

    seller_root = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="founder_ledger_sales",
    )

    buyer_root = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="founder_ledger_purchases",
    )

    transfer_type = models.CharField(
        max_length=32,
        choices=TRANSFER_TYPE_CHOICES,
        default=TRANSFER_MINIMUM_CONVEYANCE,
    )

    sale_price_credits = models.PositiveBigIntegerField()

    platform_fee_credits = models.PositiveBigIntegerField()

    seller_proceeds_credits = models.PositiveBigIntegerField()

    wallet_transaction_ids = models.JSONField(
        default=list,
        blank=True,
    )

    previous_hash = models.CharField(
        max_length=64,
        editable=False,
    )

    record_hash = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )

    metadata_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    sale_price_credits__gte=FOUNDER_FLOOR_CREDITS
                ),
                name="founder_ledger_minimum_200_credit_conveyance",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    sale_price_credits=(
                        models.F("platform_fee_credits")
                        + models.F("seller_proceeds_credits")
                    )
                ),
                name="founder_ledger_settlement_balances",
            ),
        ]

    def __str__(self):
        return (
            f"Founder ledger #{self.sequence}: "
            f"@{self.handle_snapshot}"
        )


class FounderLedgerHead(models.Model):
    """
    Singleton serialization point for the Founder hash chain.

    The row is locked with SELECT ... FOR UPDATE whenever a new
    ownership ledger record is appended.
    """

    key = models.CharField(
        max_length=32,
        unique=True,
        default="founder",
        editable=False,
    )

    last_sequence = models.PositiveBigIntegerField(
        default=0,
        editable=False,
    )

    last_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        editable=False,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return (
            f"Founder Ledger Head "
            f"#{self.last_sequence}"
        )

class FounderListing(models.Model):
    """
    Marketplace listing for one transferable Founder property.

    A Founder property may have at most one active listing.
    One owner/root may list unlimited different Founder properties.
    """

    SOURCE_P2P = "p2p"
    SOURCE_TIENDA = "tienda"

    SOURCE_CHOICES = [
    (SOURCE_P2P, "P2P Marketplace"),
    (SOURCE_TIENDA, "Founder Tienda"),
    ]

    TIENDA_FIXED = "fixed"
    TIENDA_BLIND = "blind"
    TIENDA_SWAMP = "swamp"

    TIENDA_LANE_CHOICES = [
    (TIENDA_FIXED, "Fixed Price"),
    (TIENDA_BLIND, "Blind Offer"),
    (TIENDA_SWAMP, "Swamp Land"),
]
    SALE_FIXED = "fixed"
    SALE_BLIND = "blind"

    SALE_TYPE_CHOICES = [
        (SALE_FIXED, "Fixed Price"),
        (SALE_BLIND, "Blind Sale"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_SOLD = "sold"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_SOLD, "Sold"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    founder_account = models.ForeignKey(
        FounderAccount,
        on_delete=models.PROTECT,
        related_name="listings",
    )

    seller_root = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="founder_listings",
    )

    listing_source = models.CharField(
        max_length=16,
        choices=SOURCE_CHOICES,
        default=SOURCE_P2P,
    )

    tienda_lane = models.CharField(
        max_length=16,
        choices=TIENDA_LANE_CHOICES,
        null=True,
        blank=True,
    )


    sale_type = models.CharField(
        max_length=16,
        choices=SALE_TYPE_CHOICES,
    )

    fixed_price_credits = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    minimum_bid_credits = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    starts_at = models.DateTimeField(
        default=timezone.now,
    )

    ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["founder_account"],
                condition=models.Q(status="active"),
                name="unique_active_founder_listing_per_asset",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        sale_type="fixed",
                        fixed_price_credits__gte=FOUNDER_FLOOR_CREDITS,
                    )
                    |
                    models.Q(
                        sale_type="blind",
                        minimum_bid_credits__gte=FOUNDER_FLOOR_CREDITS,
                    )
                ),
                name="founder_listing_minimum_200_credits",
            ),

            models.CheckConstraint(
                condition=(
                models.Q(
                    listing_source="p2p",
                    tienda_lane__isnull=True,
                )
                |
                models.Q(
                    listing_source="tienda",
                    tienda_lane__isnull=False,
        )
    ),
            name="founder_listing_tienda_lane_matches_source",
),

            models.CheckConstraint(
                condition=(
                    ~models.Q(tienda_lane="swamp")
                    |
                    models.Q(
                        sale_type="fixed",
                        fixed_price_credits=FOUNDER_FLOOR_CREDITS,
                    )
                ),
                name="founder_tienda_swamp_exactly_200_fixed",
            ),
        ]

    def __str__(self):
        return (
            f"@{self.founder_account.handle} "
            f"{self.get_sale_type_display()} "
            f"[{self.status}]"
        )

#end
