from django.core.management.base import BaseCommand

from auctions.models import PaymentIntent
from auctions.payment_services import (
    PaymentFulfillmentError,
    fulfill_payment_intent,
)


class Command(BaseCommand):
    help = "Fulfill settled, unfulfilled FANZ payment intents."

    def handle(self, *args, **options):
        intent_ids = list(
            PaymentIntent.objects.filter(
                status="settled",
                fulfilled_at__isnull=True,
            )
            .order_by("id")
            .values_list("id", flat=True)
        )

        if not intent_ids:
            return

        fulfilled_count = 0
        skipped_count = 0
        failed_count = 0

        for intent_id in intent_ids:
            try:
                intent, created = fulfill_payment_intent(intent_id)

                if created:
                    fulfilled_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Fulfilled PaymentIntent {intent.pk} "
                            f"({intent.purpose})"
                        )
                    )
                else:
                    skipped_count += 1

            except PaymentFulfillmentError as exc:
                failed_count += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"PaymentIntent {intent_id} not fulfilled: {exc}"
                    )
                )

            except Exception as exc:
                # Isolate unexpected failures so one bad payment cannot
                # prevent other settled payments from being fulfilled.
                failed_count += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"PaymentIntent {intent_id} failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
                )

        self.stdout.write(
            "Payment fulfillment: "
            f"fulfilled={fulfilled_count} "
            f"skipped={skipped_count} "
            f"failed={failed_count}"
        )
