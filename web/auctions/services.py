from django.contrib.auth import get_user_model
from .models import Notification, Conversation, DirectMessage
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.core.mail import send_mail
from django.conf import settings
from .models import Auction, Bid, BidWallet
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
                f"😡 You Were Outbid!\n"
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
                f"📣 You were outbid!\n\n" 
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

        Notification.objects.create(
            user=auction.winner,
            actor=None,
            notification_type=Notification.AUCTION,
            message=f"🏆 You're a Winner!\n\n{auction.title}\n\nDownload link inside."
        )

        User = get_user_model()
        platform_sender = User.objects.get(username="platform")

        delivery_link = ""
        if auction.digital_item and auction.digital_item.delivery_url:
            delivery_link = (
                f"\n\n📦 Download your item:\n"
                f"{auction.digital_item.delivery_url}"
            )

        conversation = Conversation.objects.create()
        conversation.participants.add(platform_sender, auction.winner)

        DirectMessage.objects.create(
            conversation=conversation,
            sender=platform_sender,
            body=f"🎉 You're a Winner!\n\n{auction.title}!{delivery_link}",
        )

        auction.winner_email_sent = True
        auction.save(update_fields=["winner_email_sent"])

    return auction


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
