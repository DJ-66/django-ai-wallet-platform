import csv
from pathlib import Path

from .category_normalizer import normalize_category
from .import_services import BusinessImportRecord


FANZ_REQUIRED_COLUMNS = {
    "name",
    "source_external_id",
}

FANZ_OPTIONAL_COLUMNS = {
    "industry",
    "category",
    "description",
    "address",
    "city",
    "country",
    "website_url",
    "phone",
    "email",
    "source_url",
    "discovery_hub_slug",
}

FANZ_SUPPORTED_COLUMNS = (
    FANZ_REQUIRED_COLUMNS | FANZ_OPTIONAL_COLUMNS
)

GOOGLE_REQUIRED_COLUMNS = {
    "title",
    "primary_category",
    "place_id",
}

GOOGLE_FORMAT_MARKERS = {
    "title",
    "primary_category",
    "place_id",
    "address",
}


class BusinessCSVError(ValueError):
    """Raised when a business CSV file cannot be parsed safely."""


def _clean_header(value):
    return str(value or "").strip().lower()


def _clean_value(value):
    return str(value or "").strip()


def _detect_csv_format(headers):
    header_set = set(headers)

    if GOOGLE_REQUIRED_COLUMNS.issubset(header_set):
        return "google_maps"

    if FANZ_REQUIRED_COLUMNS.issubset(header_set):
        return "fanz"

    raise BusinessCSVError(
        "CSV format was not recognized. Expected either "
        "FANZ business columns or Google Maps export columns."
    )


def _resolve_industry(category, row_number):
    industry = normalize_category(category) or ""

    if not industry:
        raise BusinessCSVError(
            f"Row {row_number}: unknown category: {category}"
        )

    return industry


def _build_fanz_record(values, source_name, row_number):
    industry = values.get("industry", "")
    category = values.get("category", "")

    if not industry and category:
        industry = _resolve_industry(
            category,
            row_number,
        )

    if not industry:
        raise BusinessCSVError(
            f"Row {row_number}: industry or category is required"
        )

    return BusinessImportRecord(
        name=values.get("name", ""),
        industry=industry,
        source_name=source_name,
        source_external_id=values.get(
            "source_external_id",
            "",
        ),
        description=values.get("description", ""),
        address=values.get("address", ""),
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


def _build_google_record(values, source_name, row_number):
    category = values.get("primary_category", "")
    industry = _resolve_industry(
        category,
        row_number,
    )

    description_parts = []

    if category:
        description_parts.append(
            f"Community business category: {category}."
        )

    description = " ".join(description_parts)

    return BusinessImportRecord(
        name=values.get("title", ""),
        industry=industry,
        source_name=source_name,
        source_external_id=values.get("place_id", ""),
        description=description,
        address=values.get("address", ""),
        city=values.get("city", ""),
        country=values.get("country", ""),
        website_url=values.get("website", ""),
        phone=values.get("phone", ""),
        email=values.get("email", ""),
        source_url=values.get("url", ""),
        discovery_hub_slug="",
    )


def read_business_csv(path, source_name):
    """
    Yield normalized BusinessImportRecord objects from a UTF-8 CSV.

    Supported formats:
    - FANZ-native business CSV
    - Google Maps business export CSV
    """
    path = Path(path)
    source_name = _clean_value(source_name)

    if not source_name:
        raise BusinessCSVError("source_name is required")

    if not path.exists():
        raise BusinessCSVError(
            f"CSV file does not exist: {path}"
        )

    if not path.is_file():
        raise BusinessCSVError(
            f"CSV path is not a file: {path}"
        )

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

        if len(normalized_headers) != len(
            set(normalized_headers)
        ):
            raise BusinessCSVError(
                "CSV file contains duplicate column names"
            )

        csv_format = _detect_csv_format(
            normalized_headers
        )

        if csv_format == "fanz":
            missing_columns = (
                FANZ_REQUIRED_COLUMNS
                - set(normalized_headers)
            )

            if missing_columns:
                missing = ", ".join(
                    sorted(missing_columns)
                )
                raise BusinessCSVError(
                    "CSV file is missing required columns: "
                    f"{missing}"
                )

            unsupported_columns = (
                set(normalized_headers)
                - FANZ_SUPPORTED_COLUMNS
            )

            if unsupported_columns:
                unsupported = ", ".join(
                    sorted(unsupported_columns)
                )
                raise BusinessCSVError(
                    "CSV file contains unsupported columns: "
                    f"{unsupported}"
                )

        reader.fieldnames = normalized_headers

        for row_number, row in enumerate(
            reader,
            start=2,
        ):
            values = {
                key: _clean_value(value)
                for key, value in row.items()
                if key is not None
            }

            if not any(values.values()):
                continue

            if csv_format == "google_maps":
                record = _build_google_record(
                    values,
                    source_name,
                    row_number,
                )
            else:
                record = _build_fanz_record(
                    values,
                    source_name,
                    row_number,
                )

            yield row_number, record
