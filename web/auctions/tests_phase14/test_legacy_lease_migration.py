"""Verify AI lease migration in Django's disposable test database."""

from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

from auctions.models import LegacyAIPublicationLease


class LegacyAILeaseMigrationTests(TransactionTestCase):

    def test_lease_schema_and_migration_record(self):
        table = LegacyAIPublicationLease._meta.db_table

        self.assertIn(
            table,
            connection.introspection.table_names(),
        )

        self.assertTrue(
            MigrationRecorder(connection).migration_qs.filter(
                app="auctions",
                name="0116_legacy_ai_publication_lease",
            ).exists()
        )

        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor,
                    table,
                )
            }

        required = {
            "publication_id",
            "claim_token",
            "claimed_at",
            "lease_expires_at",
            "next_retry_at",
            "attempt_count",
            "last_error",
        }

        self.assertTrue(required.issubset(columns))

        print("Migration 0116: PASS")
        print("Lease table: PRESENT")
        print("Required columns: PASS")
