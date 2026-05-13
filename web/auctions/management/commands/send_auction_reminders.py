from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from auctions.models import Auction


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
            bidders = (
                auction.bids
                .select_related("user")
                .values_list("user__email", flat=True)
                .distinct()
            )

            emails = [email for email in bidders if email]

            if emails:
                send_mail(
                    subject=f"Less than 60 minutes left: {auction.title}",
                    message=(
                        f"{auction.title} ends in less than 60 minutes.\n\n"
                        f"Current price: {auction.current_price.quantize(Decimal('1'))} credits\n"
                        f"Bid here:\n"
                        f"https://django.usdrick.com/auctions/{auction.id}/"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=emails,
                    fail_silently=True,
                )

            auction.reminder_60_sent = True
            auction.save(update_fields=["reminder_60_sent"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {auctions.count()} auction reminders."
            )
        )

