from django.contrib.auth import get_user_model
from .models import Notification, Conversation, DirectMessage
from datetime import timedelta
from django.db.models import BooleanField, Exists, OuterRef, Subquery, Value
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.core.mail import send_mail
from django.conf import settings
from .models import Auction, Bid
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .utils import get_system_wallet

from .models import (
    BidWallet,
    CreditPurchase,
    WalletTransaction,
    CreditPackage,
)

def send_winner_email(auction):
    if not auction.winner or not auction.winner.email:
        return

    delivery_url = ""

    if auction.digital_item and auction.digital_item.delivery_url:
        delivery_url = auction.digital_item.delivery_url

    html_content = render_to_string(
        "emails/auction_winner.html",
        {
            "user": auction.winner,
            "auction": auction,
            "delivery_url": delivery_url,
            "site_url": "https://fanz.to",
        },
    )

    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject=f"🎉 You Won: {auction.title}",
        body=text_content,
        to=[auction.winner.email],
    )

    email.attach_alternative(html_content, "text/html")
    email.send()

def send_digital_delivery_message(user, auction, event_type="buy_now"):
    User = get_user_model()
    platform_sender = User.objects.get(username="platform")

    delivery_link = ""
    if auction.digital_item and auction.digital_item.delivery_url:
        delivery_link = (
            f"\n\n📦 Download your item:\n"
            f"{auction.digital_item.delivery_url}"
        )

    if event_type == "auction_win":
        notification_message = (
            f"🏆 You're a Winner!\n\n{auction.title}\n\nDownload link inside."
        )
        dm_body = f"🎉 You're a Winner!\n\n{auction.title}!{delivery_link}"
    else:
        notification_message = (
            f"🎉 Purchase Complete!\n\n{auction.title}\n\nDownload link inside."
        )
        dm_body = f"🎉 Purchase Complete!\n\n{auction.title}!{delivery_link}"

    Notification.objects.create(
        user=user,
        actor=None,
        notification_type=Notification.AUCTION,
        message=notification_message,
    )

    conversation = Conversation.objects.create()
    conversation.participants.add(platform_sender, user)

    DirectMessage.objects.create(
        conversation=conversation,
        sender=platform_sender,
        body=dm_body,
    )


@transaction.atomic
def place_bid(auction_id, user):
    auction = Auction.objects.select_for_update().get(id=auction_id)
    wallet = BidWallet.objects.select_for_update().get(user=user)

    previous_bid = auction.bids.order_by("-created_at").first()
    now = timezone.now()

    if auction.status != "live":
        raise ValidationError("Auction is not live.")

    if not (auction.starts_at <= now < auction.ends_at):
        raise ValidationError("Auction not active.")

    if wallet.credits <= 0:
        raise ValidationError("No credits remaining.")

    platform_wallet = get_system_wallet()

    wallet.credits -= 1
    platform_wallet.credits += 1

    wallet.save(update_fields=["credits"])
    platform_wallet.save(update_fields=["credits"])

    new_price = auction.current_price + auction.bid_increment

    Bid.objects.create(
        auction=auction,
        user=user,
        amount=new_price,
    )

    WalletTransaction.objects.create(
        sender=wallet,
        receiver=platform_wallet,
        amount=1,
        transaction_type="game",
        reference=f"Bid on auction #{auction.id}: {auction.title}",
)

    auction.current_price = new_price

    if (auction.ends_at - now) <= timedelta(seconds=45):
        auction.ends_at += timedelta(seconds=15)

    auction.save(update_fields=["current_price", "ends_at"])

    if previous_bid and previous_bid.user != user and previous_bid.user.email:
        

        auction_url = f"https://fanz.to/auctions/{auction.id}/"

        context = {
                "user": previous_bid.user,
                "auction": auction,
                "auction_url": auction_url,
        }

        text_body = render_to_string("emails/outbid.txt", context)
        html_body = render_to_string("emails/outbid.html", context)

        email = EmailMultiAlternatives(
            subject=f"You were outbid on {auction.title}",
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[previous_bid.user.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)
        
        Notification.objects.create(
            user=previous_bid.user,
            actor=user,
            notification_type=Notification.MESSAGE,
            message=(
                f"📣 You Were Outbid!\n"
                f"{auction.title}\n"
                f"Tap to bid again."
            ),
        )

        User = get_user_model()
        platform_sender = User.objects.get(username="platform")

        conversation = Conversation.objects.create()
        conversation.participants.add(platform_sender, previous_bid.user)

        DirectMessage.objects.create(
            conversation=conversation,
            sender=platform_sender,
            body=(
                f"😡 You were outbid!\n\n"
                f"{auction.title}.\n\n"
                f"Bid again here:\n"
                f"{auction_url}"
            ),
        )

    return auction


@transaction.atomic
def close_auction(auction_id):
    auction = Auction.objects.select_for_update().get(id=auction_id)

    if auction.status == "ended":
        return auction

    now = timezone.now()

    if now < auction.ends_at:
        raise ValidationError("Auction has not ended yet.")

    last_bid = auction.bids.order_by("-created_at").first()

    if last_bid:
        auction.winner = last_bid.user

    auction.status = "ended"
    auction.save(update_fields=["status", "winner"])

    if auction.winner and not auction.winner_email_sent:
        send_winner_email(auction)

        send_digital_delivery_message(
            user=auction.winner,
            auction=auction,
            event_type="auction_win",
        )

        auction.winner_email_sent = True
        auction.save(update_fields=["winner_email_sent"])

    return auction


def prepare_auction_cards(
    auctions,
    user,
    now=None,
    language=None,
):
    """
    Prepare auctions for reusable card rendering.

    Adds countdown, favorite, and high-bidder presentation data
    without issuing separate queries for every auction.
    """
    from django.utils import timezone

    from .models import Bid, FavoriteAuction

    if now is None:
        now = timezone.now()

    latest_bid_user = (
        Bid.objects
        .filter(auction_id=OuterRef("pk"))
        .order_by("-created_at")
        .values("user_id")[:1]
    )

    auctions = auctions.annotate(
        last_bid_user_id=Subquery(latest_bid_user),
    )

    if user.is_authenticated:
        favorite = FavoriteAuction.objects.filter(
            user=user,
            auction_id=OuterRef("pk"),
        )

        auctions = auctions.annotate(
            is_favorited=Exists(favorite),
        )
    else:
        auctions = auctions.annotate(
            is_favorited=Value(
                False,
                output_field=BooleanField(),
            ),
        )
    if language:
        language = str(language).lower().split("-")[0]

        if language not in ("en", "es", "pt"):
            language = "en"

        auctions = auctions.prefetch_related(
            "translations",
        )
    prepared_auctions = list(auctions)

    for auction in prepared_auctions:
        remaining = (
            auction.ends_at - now
        ).total_seconds()
        auction.seconds_remaining = max(
            0,
            int(remaining),
        )
        auction.is_high_bidder = bool(
            user.is_authenticated
            and auction.last_bid_user_id == user.id
        )

        # Canonical fallbacks.
        auction.display_title = auction.title
        auction.display_description = ""
        auction.localized_hero_image = None

        if language:
            translation = next(
                (
                    item
                    for item in auction.translations.all()
                    if item.language == language
                ),
                None,
            )

            if translation:
                if translation.title:
                     auction.display_title = translation.title

                if translation.description:
                    auction.display_description = (
                        translation.description
                    )

                if (
                    translation.use_language_hero
                    and translation.hero_image
                ):
                    auction.localized_hero_image = (
                        translation.hero_image
                    )
    return prepared_auctions


def prepare_feed_posts(posts, language=None):
    """
    Prepare feed posts for localized presentation.

    Adds display_title and display_content while preserving
    canonical post fields as fallbacks.
    """

    if language:
        language = str(language).lower().split("-")[0]

        if language not in ("en", "es", "pt"):
            language = "en"

        posts = posts.prefetch_related("translations")

    prepared_posts = list(posts)

    for post in prepared_posts:
        post.display_title = post.title
        post.display_content = post.content

        if language:
            translation = next(
                (
                    item
                    for item in post.translations.all()
                    if item.language == language
                ),
                None,
            )

            if translation:
                if translation.title:
                    post.display_title = translation.title

                if translation.content:
                    post.display_content = translation.content

    return prepared_posts


def calculate_node_commission(node, package):
    """
    Returns commission amount in USD based on package price.
    """
    if not node or not node.commission_rate:
        return Decimal("0.00")

    return (package.price_usd * node.commission_rate).quantize(Decimal("0.01"))


def calculate_node_commission(node, package):
    if not node or not node.commission_rate:
        return Decimal("0.00")

    return (package.price_usd * node.commission_rate).quantize(Decimal("0.01"))


@transaction.atomic
def process_credit_purchase(*, user, package, external_id, source_node=None):
    """
    Safely processes a credit purchase.

    Rules:
    - external_id prevents duplicate purchases
    - credits user wallet
    - logs purchase
    - calculates node commission if source_node exists
    """

    if CreditPurchase.objects.filter(external_id=external_id).exists():
        return CreditPurchase.objects.get(external_id=external_id), False

    wallet, _ = BidWallet.objects.select_for_update().get_or_create(user=user)

    purchase = CreditPurchase.objects.create(
        user=user,
        wallet=wallet,
        package=package,
        amount_paid=package.price_usd,
        external_id=external_id,
        source_type="node" if source_node else "direct",
        source_node=source_node,
    )


    commission_amount = calculate_node_commission(source_node, package)

    if source_node and commission_amount > 0:
        node_wallet, _ = BidWallet.objects.select_for_update().get_or_create(
            user=source_node.user
    )

    # Current simple rule:
    # $1 commission = 1 platform credit
        commission_credits = int(package.credits * source_node.commission_rate)

        if commission_credits > 0:
            node_wallet.credits += commission_credits
            node_wallet.save()

            WalletTransaction.objects.create(
                sender=node_wallet,
                receiver=node_wallet,
                amount=commission_credits,
                transaction_type="commission",
                reference=f"Commission:{purchase.id}",
                )

    wallet.credits += package.credits
    wallet.save()

    WalletTransaction.objects.create(
        sender=wallet,
        receiver=wallet,
        amount=package.credits,
        transaction_type="purchase",
        reference=f"Purchase:{purchase.id}",
     )

    commission_amount = calculate_node_commission(source_node, package)

    # We calculate this now, but do NOT mint commission credits yet
    # until we decide whether commission is paid in USD or credits.

    return purchase, True


def _get_public_hashtag_post_queryset(hashtag):
    """
    Build the shared queryset for public, free hashtag posts eligible
    for public Discovery surfaces.

    Keep Discovery eligibility rules here so listing and metric
    capabilities cannot drift apart.
    """
    from django.db.models import Count, Q

    from .models import FeedPost, FeedPostMedia

    return (
        FeedPost.objects
        .filter(
            hashtags=hashtag,
            is_public=True,
            is_paid=False,
        )
        .annotate(
            active_image_count=Count(
                "media",
                filter=Q(
                    media__is_active=True,
                    media__media_type=FeedPostMedia.MEDIA_TYPE_IMAGE,
                ),
                distinct=True,
            ),
            forbidden_media_count=Count(
                "media",
                filter=Q(
                    media__is_active=True,
                    media__media_type__in=[
                        FeedPostMedia.MEDIA_TYPE_VIDEO,
                        FeedPostMedia.MEDIA_TYPE_AUDIO,
                        FeedPostMedia.MEDIA_TYPE_PDF,
                    ],
                ),
                distinct=True,
            ),
        )
        .filter(
            forbidden_media_count=0,
            active_image_count__lte=3,
        )
        .filter(
            Q(active_image_count__gte=1)
            |
            (
                Q(image__isnull=False)
                & ~Q(image="")
            )
        )
    )


def get_public_hashtag_posts(hashtag, limit=None):
    """
    Return public, free hashtag posts eligible for public discovery surfaces.

    This queryset is shared by hashtag feeds, Discovery Hubs, and future
    search, syndication, API, and AI consumers.
    """
    queryset = (
        _get_public_hashtag_post_queryset(hashtag)
        .select_related(
            "user",
            "user__profile",
            "user__bidwallet",
        )
        .prefetch_related(
            "media",
            "hashtags",
            "likes",
        )
        .order_by("-created_at")
    )

    if limit is not None:
        queryset = queryset[:limit]

    return queryset


def get_public_hashtag_post_count(hashtag):
    """
    Return the total number of public, free hashtag posts eligible
    for public Discovery surfaces.
    """
    return _get_public_hashtag_post_queryset(hashtag).count()
