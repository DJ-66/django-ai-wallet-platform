import csv
from pathlib import Path

from .import_services import BusinessImportRecord


REQUIRED_COLUMNS = {
    "name",
    "industry",
    "source_external_id",
}

OPTIONAL_COLUMNS = {
    "description",
    "city",
    "country",
    "website_url",
    "phone",
    "email",
    "source_url",
    "discovery_hub_slug",
}

SUPPORTED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


class BusinessCSVError(ValueError):
    """Raised when a business CSV file cannot be parsed safely."""


def _clean_header(value):
    return str(value or "").strip().lower()


def _clean_value(value):
    return str(value or "").strip()


def read_business_csv(path, source_name):
    """
    Yield BusinessImportRecord objects from a UTF-8 CSV file.

    The external source name is supplied by the command rather than
    repeated in every CSV row.
    """
    path = Path(path)
    source_name = _clean_value(source_name)

    if not source_name:
        raise BusinessCSVError("source_name is required")

    if not path.exists():
        raise BusinessCSVError(f"CSV file does not exist: {path}")

    if not path.is_file():
        raise BusinessCSVError(f"CSV path is not a file: {path}")

    try:
        csv_file = path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        )
    except OSError as exc:
        raise BusinessCSVError(
            f"Could not open CSV file: {path}"
        ) from exc

    with csv_file:
        reader = csv.DictReader(csv_file)

        if reader.fieldnames is None:
            raise BusinessCSVError(
                "CSV file must contain a header row"
            )

        normalized_headers = [
            _clean_header(header)
            for header in reader.fieldnames
        ]

        if len(normalized_headers) != len(set(normalized_headers)):
            raise BusinessCSVError(
                "CSV file contains duplicate column names"
            )

        missing_columns = REQUIRED_COLUMNS - set(
            normalized_headers
        )

        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise BusinessCSVError(
                f"CSV file is missing required columns: {missing}"
            )

        unsupported_columns = (
            set(normalized_headers) - SUPPORTED_COLUMNS
        )

        if unsupported_columns:
            unsupported = ", ".join(
                sorted(unsupported_columns)
            )
            raise BusinessCSVError(
                f"CSV file contains unsupported columns: "
                f"{unsupported}"
            )

        reader.fieldnames = normalized_headers

        for row_number, row in enumerate(reader, start=2):
            values = {
                key: _clean_value(value)
                for key, value in row.items()
                if key is not None
            }

            if not any(values.values()):
                continue

            record = BusinessImportRecord(
                name=values.get("name", ""),
                industry=values.get("industry", ""),
                source_name=source_name,
                source_external_id=values.get(
                    "source_external_id",
                    "",
                ),
                description=values.get("description", ""),
                city=values.get("city", ""),
                country=values.get("country", ""),
                website_url=values.get("website_url", ""),
                phone=values.get("phone", ""),
                email=values.get("email", ""),
                source_url=values.get("source_url", ""),
                discovery_hub_slug=values.get(
                    "discovery_hub_slug",
                    "",
                ),
            )

            yield row_number, record
