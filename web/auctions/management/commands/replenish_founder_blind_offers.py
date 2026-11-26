"""Recover missing Founder Tienda Blind Offers safely."""

from django.core.management.base import BaseCommand

from auctions.founder_blind_replenishment import (
    replenish_blind_offers,
)


class Command(BaseCommand):
    help = (
        "Replenish missing Founder Tienda Blind Offers "
        "from eligible existing Treasury inventory."
    )

    def handle(self, *args, **options):
        result = replenish_blind_offers()

        message = (
            "Founder Blind Offer recovery: "
            f"target={result['target']} "
            f"active_before={result['active_before']} "
            f"created={result['created']} "
            f"active_after={result['active_after']} "
            f"shortage={result['shortage']}"
        )

        if result["shortage"]:
            self.stdout.write(
                self.style.WARNING(message)
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(message)
            )
