"""Real PostgreSQL transaction isolation tests for AutoPost billing."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from auctions.ai_services.autopost_billing import (
    purchase_autopost_subscription,
)
from auctions.models import (
    AutoPostEntitlement,
    BidWallet,
    WalletTransaction,
)
from auctions.utils import get_system_wallet


class AutoPostBillingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="autopost_concurrent_creator"
        )
        self.wallet = BidWallet.objects.create(
            user=self.user,
            credits=500,
        )
        self.platform_wallet = get_system_wallet()
        self.platform_wallet.credits = 1000
        self.platform_wallet.save(update_fields=["credits"])

    def test_simultaneous_same_period_charges_once(self):
        self.assertEqual(connection.vendor, "postgresql")

        barrier = Barrier(2)

        def purchase():
            close_old_connections()
            try:
                account = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                entitlement, created = purchase_autopost_subscription(
                    account=account,
                    period_key="2026-10",
                )
                return entitlement.pk, created
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(purchase) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]

        self.wallet.refresh_from_db()
        self.platform_wallet.refresh_from_db()

        self.assertEqual({pk for pk, _ in results}, {
            AutoPostEntitlement.objects.get().pk
        })
        self.assertEqual(sorted(created for _, created in results), [
            False, True
        ])
        self.assertEqual(self.wallet.credits, 350)
        self.assertEqual(self.platform_wallet.credits, 1150)

        self.assertEqual(AutoPostEntitlement.objects.count(), 1)
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_type="autopost_subscription"
            ).count(),
            1,
        )
