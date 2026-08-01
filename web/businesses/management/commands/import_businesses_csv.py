from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from businesses.csv_import import (
    BusinessCSVError,
    read_business_csv,
)
from businesses.import_services import (
    BusinessImportResult,
    BusinessImportValidationError,
    import_business_record,
)


class Command(BaseCommand):
    help = (
        "Import Encarnacion business listings from a UTF-8 CSV file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            help="Path to the CSV file inside the web container.",
        )
        parser.add_argument(
            "--source-name",
            required=True,
            help=(
                "Stable source identifier, such as "
                "'encarnacion-open-data'."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Validate and process the file, then roll back all "
                "database changes."
            ),
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        source_name = options["source_name"]
        dry_run = options["dry_run"]

        result = BusinessImportResult()

        try:
            rows = read_business_csv(
                csv_path,
                source_name=source_name,
            )

            with transaction.atomic():
                for row_number, record in rows:
                    try:
                        status, business = import_business_record(
                            record
                        )
                    except BusinessImportValidationError as exc:
                        result.failed += 1
                        message = f"Row {row_number}: {exc}"
                        result.errors.append(message)
                        self.stderr.write(
                            self.style.ERROR(message)
                        )
                        continue

                    if status == "created":
                        result.created += 1
                    elif status == "updated":
                        result.updated += 1
                    elif status == "skipped":
                        result.skipped += 1

                    self.stdout.write(
                        f"Row {row_number}: "
                        f"{status} — {business.name}"
                    )

                if dry_run:
                    transaction.set_rollback(True)

        except BusinessCSVError as exc:
            raise CommandError(str(exc)) from exc

        summary = (
            f"Created: {result.created} | "
            f"Updated: {result.updated} | "
            f"Skipped: {result.skipped} | "
            f"Failed: {result.failed}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN — no changes saved. {summary}"
                )
            )
        elif result.failed:
            self.stdout.write(
                self.style.WARNING(summary)
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(summary)
            )
