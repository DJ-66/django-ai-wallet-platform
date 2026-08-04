from dataclasses import dataclass, field, replace
from typing import Iterable
from unicodedata import combining, normalize
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.utils import timezone

from auctions.models import DiscoveryHub

from .models import BusinessListing


class BusinessImportValidationError(ValueError):
    """Raised when an external business record cannot be imported."""


@dataclass(frozen=True)
class BusinessImportRegion:
    city: str
    country: str
    accepted_city_names: frozenset[str]
    accepted_country_names: frozenset[str]


ENCARNACION_IMPORT_REGION = BusinessImportRegion(
    city="Encarnación",
    country="Paraguay",
    accepted_city_names=frozenset(
        {
            "encarnacion",
            "encarnación",
        }
    ),
    accepted_country_names=frozenset(
        {
            "paraguay",
            "py",
        }
    ),
)


DISCOVERY_HUB_BY_INDUSTRY = {
    BusinessListing.INDUSTRY_RESTAURANT: "restaurants",
    BusinessListing.INDUSTRY_REAL_ESTATE: "real-estate",
    BusinessListing.INDUSTRY_LAW_FIRM: "services",
}


@dataclass(frozen=True)
class BusinessImportRecord:
    name: str
    industry: str
    source_name: str
    source_external_id: str

    description: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    website_url: str = ""
    phone: str = ""
    email: str = ""
    source_url: str = ""
    discovery_hub_slug: str = ""


@dataclass
class BusinessImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def processed(self):
        return self.created + self.updated + self.skipped + self.failed


def _collapse_whitespace(value):
    return " ".join(str(value or "").split())


def _comparison_value(value):
    value = _collapse_whitespace(value).casefold()

    return "".join(
        character
        for character in normalize("NFKD", value)
        if not combining(character)
    )


def _normalize_url(value, field_name):
    value = _collapse_whitespace(value)

    if not value:
        return ""

    if not urlsplit(value).scheme:
        value = f"https://{value}"

    try:
        URLValidator()(value)
    except ValidationError as exc:
        raise BusinessImportValidationError(
            f"{field_name} is not a valid URL: {value}"
        ) from exc

    return value


def _normalize_email(value):
    value = _collapse_whitespace(value).lower()

    if not value:
        return ""

    try:
        validate_email(value)
    except ValidationError as exc:
        raise BusinessImportValidationError(
            f"email is not valid: {value}"
        ) from exc

    return value


def _normalize_region(record, region):
    city = _collapse_whitespace(record.city)
    country = _collapse_whitespace(record.country)

    city_comparison = _comparison_value(city or region.city)
    country_comparison = _comparison_value(country or region.country)

    accepted_cities = {
        _comparison_value(value)
        for value in region.accepted_city_names
    }
    accepted_countries = {
        _comparison_value(value)
        for value in region.accepted_country_names
    }

    if city_comparison not in accepted_cities:
        raise BusinessImportValidationError(
            f"city is outside the pilot region: {city}"
        )

    if country_comparison not in accepted_countries:
        raise BusinessImportValidationError(
            f"country is outside the pilot region: {country}"
        )

    return region.city, region.country


def normalize_business_record(
    record,
    region=ENCARNACION_IMPORT_REGION,
):
    """
    Normalize and validate a source-independent business record.

    Blank city and country values default to the configured pilot region.
    Explicit values outside the pilot region are rejected.
    """
    if not isinstance(record, BusinessImportRecord):
        raise BusinessImportValidationError(
            "record must be a BusinessImportRecord"
        )

    name = _collapse_whitespace(record.name)

    if not name:
        raise BusinessImportValidationError("name is required")

    source_name = _collapse_whitespace(record.source_name).lower()
    source_external_id = _collapse_whitespace(
        record.source_external_id
    )

    if not source_name:
        raise BusinessImportValidationError("source_name is required")

    if not source_external_id:
        raise BusinessImportValidationError(
            "source_external_id is required"
        )

    valid_industries = {
        value
        for value, _label in BusinessListing.INDUSTRY_CHOICES
    }

    industry = _collapse_whitespace(record.industry).lower()

    if industry not in valid_industries:
        allowed = ", ".join(sorted(valid_industries))
        raise BusinessImportValidationError(
            f"industry must be one of: {allowed}"
        )

    city, country = _normalize_region(record, region)

    return replace(
        record,
        name=name,
        industry=industry,
        source_name=source_name,
        source_external_id=source_external_id,
        description=_collapse_whitespace(record.description),
        address=_collapse_whitespace(record.address),
        city=city,
        country=country,
        website_url=_normalize_url(
            record.website_url,
            "website_url",
        ),
        phone=_collapse_whitespace(record.phone),
        email=_normalize_email(record.email),
        source_url=_normalize_url(
            record.source_url,
            "source_url",
        ),
        discovery_hub_slug=_collapse_whitespace(
            record.discovery_hub_slug
        ).lower(),
    )


def resolve_discovery_hub(industry, explicit_slug=""):
    """
    Resolve an active Discovery Hub for an imported business.

    An explicit slug overrides the default industry mapping. This keeps
    normal imports simple while allowing exceptional listings to target
    a different compatible Discovery Hub.
    """
    explicit_slug = _collapse_whitespace(explicit_slug).lower()

    slug = explicit_slug or DISCOVERY_HUB_BY_INDUSTRY.get(industry, "")

    if not slug:
        raise BusinessImportValidationError(
            f"no Discovery Hub mapping configured for industry: {industry}"
        )

    hub = DiscoveryHub.objects.filter(
        slug=slug,
        is_active=True,
    ).first()

    if hub is None:
        raise BusinessImportValidationError(
            f"active Discovery Hub not found: {slug}"
        )

    return hub


@transaction.atomic
def import_business_record(
    record,
    region=ENCARNACION_IMPORT_REGION,
):
    """
    Create or update one imported business.

    Claimed listings retain all owner-controlled business information.
    Their import timestamp and source URL may still be refreshed.
    """
    normalized = normalize_business_record(record, region=region)
    discovery_hub = resolve_discovery_hub(
        normalized.industry,
        explicit_slug=normalized.discovery_hub_slug,
    )
    imported_at = timezone.now()

    business = (
        BusinessListing.objects
        .select_for_update()
        .filter(
            source_name=normalized.source_name,
            source_external_id=normalized.source_external_id,
        )
        .first()
    )

    if business is None:
        business = BusinessListing.objects.create(
            name=normalized.name,
            industry=normalized.industry,
            description=normalized.description,
            address=normalized.address,
            city=normalized.city,
            country=normalized.country,
            website_url=normalized.website_url,
            phone=normalized.phone,
            email=normalized.email,
            owner=None,
            is_claimed=False,
            is_active=True,
            discovery_hub=discovery_hub,
            source_name=normalized.source_name,
            source_url=normalized.source_url,
            source_external_id=normalized.source_external_id,
            is_imported=True,
            is_community=True,
            last_imported_at=imported_at,
        )
        return "created", business

    if business.is_claimed or business.owner_id is not None:
        business.source_url = normalized.source_url
        business.is_imported = True
        business.is_community = True
        business.last_imported_at = imported_at
        business.save(
            update_fields=[
                "source_url",
                "is_imported",
                "is_community",
                "last_imported_at",
                "updated_at",
            ]
        )
        return "skipped", business

    business.name = normalized.name
    business.industry = normalized.industry
    business.description = normalized.description
    business.address = normalized.address
    business.city = normalized.city
    business.country = normalized.country
    business.website_url = normalized.website_url
    business.phone = normalized.phone
    business.email = normalized.email
    business.discovery_hub = discovery_hub
    business.source_url = normalized.source_url
    business.is_imported = True
    business.is_community = True
    business.is_active = True
    business.last_imported_at = imported_at
    business.save(
        update_fields=[
            "name",
            "industry",
            "description",
            "address",
            "city",
            "country",
            "website_url",
            "phone",
            "email",
            "discovery_hub",
            "source_url",
            "is_imported",
            "is_community",
            "is_active",
            "last_imported_at",
            "updated_at",
        ]
    )

    return "updated", business


def import_business_records(
    records: Iterable[BusinessImportRecord],
    region=ENCARNACION_IMPORT_REGION,
):
    """
    Import a collection of normalized source-independent records.
    """
    result = BusinessImportResult()

    for position, record in enumerate(records, start=1):
        try:
            status, _business = import_business_record(
                record,
                region=region,
            )
        except BusinessImportValidationError as exc:
            result.failed += 1
            result.errors.append(f"Record {position}: {exc}")
            continue

        if status == "created":
            result.created += 1
        elif status == "updated":
            result.updated += 1
        elif status == "skipped":
            result.skipped += 1

    return result
