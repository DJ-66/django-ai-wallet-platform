from datetime import timedelta
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from auctions.models import Auction, FavoriteAuction, Bid, Notification, Conversation, DirectMessage
from django.contrib.auth import get_user_model


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


class Command(BaseCommand):
    help = "Close expired auctions and relist ended auctions."

    def handle(self, *args, **options):
        now = timezone.now()

        expired = Auction.objects.filter(
            status="live",
            ends_at__lte=now,
        )

        closed_count = 0

        for auction in expired:
            last_bid = auction.bids.order_by("-created_at").first()

            auction.status = "ended"

            if last_bid:
                auction.winner = last_bid.user

            auction.save(update_fields=["status", "winner"])

            if auction.winner and not auction.winner_email_sent:
                print(
                    "WINNER EMAIL:",
                    auction.title,
                    auction.winner.email,
                )

                try:
                    send_winner_email(auction)

                    Notification.objects.create(
                        user=auction.winner,
                        actor=None,
                        notification_type=Notification.AUCTION,
                        message=f"🏆 You're a Winner! ~ {auction.title}!"
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
                        body=f"🎉 You're a Winner! ~ {auction.title}!{delivery_link}",
                    )

                    auction.winner_email_sent = True
                    auction.save(update_fields=["winner_email_sent"])

                    print(
                        "WINNER EMAIL SENT:",
                        auction.id,
                        auction.title,
                    )

                except Exception as e:
                    print(
                        "WINNER EMAIL FAILED:",
                        auction.id,
                        auction.title,
                        str(e),
                    )

            closed_count += 1

        relist_cutoff = now - timedelta(
            days=settings.AUCTION_RELIST_DAYS
        )

        ended_ready = Auction.objects.filter(
            status="ended",
            ends_at__lte=relist_cutoff,
        )

        relisted_count = 0

        for auction in ended_ready:
            auction.bids.all().delete()
            FavoriteAuction.objects.filter(auction=auction).delete()
            auction.winner = None
            auction.winner_email_sent = False
            auction.status = "live"
            auction.current_price = auction.starting_price
            auction.starts_at = now
            auction.ends_at = now + timedelta(
                days=settings.AUCTION_DURATION_DAYS
            )

            if hasattr(auction, "reminder_60_sent"):
                auction.reminder_60_sent = False
                auction.save(update_fields=[
                    "winner",
                    "winner_email_sent",
                    "status",
                    "current_price",
                    "starts_at",
                    "ends_at",
                    "reminder_60_sent",
                ])
            else:
                auction.save(update_fields=[
                    "winner",
                    "winner_email_sent",
                    "status",
                    "current_price",
                    "starts_at",
                    "ends_at",
                ])

            relisted_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Closed {closed_count} auctions. "
                f"Relisted {relisted_count} auctions."
            )
        )
