import uuid
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class DigitalItem(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="digital_items/", blank=True, null=True)
    delivery_url = models.URLField(blank=True)

    def __str__(self):
        return self.title


class Auction(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("live", "Live"),
        ("ended", "Ended"),
    ]

    title = models.CharField(max_length=200)
    digital_item = models.ForeignKey(DigitalItem, on_delete=models.PROTECT)
    video = models.FileField(upload_to="auction_videos/", blank=True, null=True)
    image = models.ImageField(upload_to="auction_images/", blank=True, null=True)
    image_2 = models.ImageField(upload_to="auction_images/", blank=True, null=True)
    starting_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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

    def __str__(self):
        return self.title


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

    is_ai_influencer = models.BooleanField(default=False)

    
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

    fan_count = models.PositiveIntegerField(default=0)

    is_verified = models.BooleanField(default=False)
    is_official = models.BooleanField(default=False)
    
    is_ai_creator = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    

    def __str__(self):
        return self.display_name or self.user.username



class FeedPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    title = models.CharField(
        max_length=120,
        blank=True,
        default=""
    )

    content = models.TextField(max_length=2000)

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
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

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
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    generated_by_ai = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender.username} in conversation {self.conversation_id}"
