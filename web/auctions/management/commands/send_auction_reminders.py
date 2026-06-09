from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from auctions.models import Auction, FavoriteAuction


class Command(BaseCommand):
    help = "Send auction reminder emails for auctions ending within 60 minutes."

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now + timedelta(minutes=60)

        auctions = Auction.objects.filter(
            status="live",
            ends_at__gt=now,
            ends_at__lte=cutoff,
            reminder_60_sent=False,
        )

        for auction in auctions:
            bidder_emails = (
                auction.bids
                .select_related("user")
                .values_list("user__email", flat=True)
                .distinct()
            )

            watcher_emails = (
                FavoriteAuction.objects
                .filter(auction=auction)
                .select_related("user")
                .values_list("user__email", flat=True)
                .distinct()
            )

            emails = list({
                email
                for email in list(bidder_emails) + list(watcher_emails)
                if email
            })

            if emails:
                auction_url = f"https://fanz.to/auctions/{auction.id}/"

                context = {
                    "auction": auction,
                    "auction_url": auction_url,
                }

                text_body = render_to_string(
                    "emails/ending_soon.txt",
                    context,
                )

                html_body = render_to_string(
                    "emails/ending_soon.html",
                    context,
                )

                email = EmailMultiAlternatives(
                    subject=f"Less than 60 minutes left: {auction.title}",
                    body=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=emails,
                )

                email.attach_alternative(html_body, "text/html")
                email.send(fail_silently=True)

            auction.reminder_60_sent = True
            auction.save(update_fields=["reminder_60_sent"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {auctions.count()} auction reminders."
            )
        )

