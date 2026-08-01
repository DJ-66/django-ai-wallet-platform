import csv
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from .import_services import (
    BusinessImportRecord,
    BusinessImportValidationError,
    import_business_record,
    import_business_records,
    normalize_business_record,
    resolve_discovery_hub,
)
from .models import BusinessListing
from .category_normalizer import (
    normalize_category,
    normalize_category_key,
)


def create_standard_discovery_hubs():
    from auctions.models import DiscoveryHub

    hubs = {}

    for slug, title in (
        ("restaurants", "Restaurants"),
        ("real-estate", "Real Estate"),
        ("services", "Services"),
    ):
        hub, _created = DiscoveryHub.objects.get_or_create(
            slug=slug,
            defaults={
                "hashtag": slug,
                "title": title,
                "is_active": True,
            },
        )
        hubs[slug] = hub

    return hubs


class BusinessImportServiceTests(TestCase):
    def setUp(self):
        self.discovery_hubs = create_standard_discovery_hubs()

    def make_record(self, **overrides):
        values = {
            "name": "  Café Paraná  ",
            "industry": BusinessListing.INDUSTRY_RESTAURANT,
            "source_name": "Open Data Test",
            "source_external_id": "restaurant-001",
            "description": "  Local café in Encarnación.  ",
            "city": "Encarnacion",
            "country": "PY",
            "website_url": "example.com",
            "email": "INFO@EXAMPLE.COM",
            "source_url": "data.example.com/business/001",
        }
        values.update(overrides)
        return BusinessImportRecord(**values)

    def test_normalizer_uses_canonical_encarnacion_values(self):
        normalized = normalize_business_record(self.make_record())

        self.assertEqual(normalized.name, "Café Paraná")
        self.assertEqual(normalized.city, "Encarnación")
        self.assertEqual(normalized.country, "Paraguay")
        self.assertEqual(normalized.source_name, "open data test")
        self.assertEqual(normalized.email, "info@example.com")
        self.assertEqual(
            normalized.website_url,
            "https://example.com",
        )

    def test_blank_geography_defaults_to_encarnacion(self):
        normalized = normalize_business_record(
            self.make_record(city="", country="")
        )

        self.assertEqual(normalized.city, "Encarnación")
        self.assertEqual(normalized.country, "Paraguay")

    def test_record_outside_encarnacion_is_rejected(self):
        with self.assertRaises(BusinessImportValidationError):
            normalize_business_record(
                self.make_record(city="Asunción")
            )

    def test_import_creates_unclaimed_business(self):
        status, business = import_business_record(
            self.make_record()
        )

        self.assertEqual(status, "created")
        self.assertIsNone(business.owner)
        self.assertFalse(business.is_claimed)
        self.assertTrue(business.is_imported)
        self.assertTrue(business.is_active)
        self.assertEqual(business.city, "Encarnación")
        self.assertEqual(business.country, "Paraguay")
        self.assertIsNotNone(business.last_imported_at)

    def test_reimport_updates_unclaimed_business(self):
        import_business_record(self.make_record())

        status, business = import_business_record(
            self.make_record(
                name="Café Paraná Actualizado",
                phone="+595 981 555 555",
            )
        )

        self.assertEqual(status, "updated")
        self.assertEqual(
            BusinessListing.objects.count(),
            1,
        )
        self.assertEqual(
            business.name,
            "Café Paraná Actualizado",
        )
        self.assertEqual(
            business.phone,
            "+595 981 555 555",
        )

    def test_reimport_preserves_claimed_business_content(self):
        _status, business = import_business_record(
            self.make_record()
        )

        user = get_user_model().objects.create_user(
            username="business-owner",
            password="test-password",
        )

        business.owner = user
        business.is_claimed = True
        business.name = "Owner Controlled Name"
        business.phone = "+595 999 000 000"
        business.save()

        status, business = import_business_record(
            self.make_record(
                name="External Changed Name",
                phone="+595 111 111 111",
                source_url="updated.example.com/record",
            )
        )

        business.refresh_from_db()

        self.assertEqual(status, "skipped")
        self.assertEqual(
            business.name,
            "Owner Controlled Name",
        )
        self.assertEqual(
            business.phone,
            "+595 999 000 000",
        )
        self.assertEqual(
            business.source_url,
            "https://updated.example.com/record",
        )

    def test_batch_result_reports_created_and_failed(self):
        result = import_business_records(
            [
                self.make_record(),
                self.make_record(
                    source_external_id="restaurant-002",
                    city="Asunción",
                ),
            ]
        )

        self.assertEqual(result.created, 1)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.processed, 2)
        self.assertEqual(len(result.errors), 1)


    def test_resolver_maps_restaurant_to_restaurants_hub(self):
        from auctions.models import DiscoveryHub

        hub = DiscoveryHub.objects.get(slug="restaurants")

        resolved = resolve_discovery_hub(
            BusinessListing.INDUSTRY_RESTAURANT
        )

        self.assertEqual(resolved, hub)

    def test_explicit_hub_slug_overrides_industry_mapping(self):
        from auctions.models import DiscoveryHub

        default_hub = DiscoveryHub.objects.get(slug="restaurants")

        override_hub = DiscoveryHub.objects.create(
            hashtag="coffee",
            slug="coffee",
            title="Coffee",
            is_active=True,
        )

        resolved = resolve_discovery_hub(
            BusinessListing.INDUSTRY_RESTAURANT,
            explicit_slug="coffee",
        )

        self.assertNotEqual(resolved, default_hub)
        self.assertEqual(resolved, override_hub)



class BusinessCSVImportTests(TestCase):
    def setUp(self):
        self.discovery_hubs = create_standard_discovery_hubs()

    def write_csv(self, rows, fieldnames=None):
        if fieldnames is None:
            fieldnames = [
                "name",
                "industry",
                "source_external_id",
                "description",
                "city",
                "country",
                "website_url",
                "phone",
                "email",
                "source_url",
                "discovery_hub_slug",
            ]

        temporary_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".csv",
            delete=False,
        )

        with temporary_file:
            writer = csv.DictWriter(
                temporary_file,
                fieldnames=fieldnames,
            )
            writer.writeheader()
            writer.writerows(rows)

        self.addCleanup(
            Path(temporary_file.name).unlink,
            missing_ok=True,
        )

        return temporary_file.name

    def test_csv_command_creates_business(self):
        csv_path = self.write_csv(
            [
                {
                    "name": "Restaurante Costanera",
                    "industry": "restaurant",
                    "source_external_id": "rest-001",
                    "city": "Encarnacion",
                    "country": "PY",
                }
            ]
        )

        call_command(
            "import_businesses_csv",
            csv_path,
            source_name="encarnacion-test",
        )

        business = BusinessListing.objects.get(
            source_name="encarnacion-test",
            source_external_id="rest-001",
        )

        self.assertEqual(
            business.name,
            "Restaurante Costanera",
        )
        self.assertEqual(
            business.city,
            "Encarnación",
        )
        self.assertFalse(business.is_claimed)
        self.assertTrue(business.is_imported)

    def test_csv_command_dry_run_rolls_back(self):
        csv_path = self.write_csv(
            [
                {
                    "name": "Dry Run Restaurant",
                    "industry": "restaurant",
                    "source_external_id": "dry-001",
                }
            ]
        )

        call_command(
            "import_businesses_csv",
            csv_path,
            source_name="encarnacion-test",
            dry_run=True,
        )

        self.assertFalse(
            BusinessListing.objects.filter(
                source_name="encarnacion-test",
                source_external_id="dry-001",
            ).exists()
        )

    def test_csv_command_rejects_outside_region(self):
        csv_path = self.write_csv(
            [
                {
                    "name": "Asuncion Restaurant",
                    "industry": "restaurant",
                    "source_external_id": "outside-001",
                    "city": "Asunción",
                    "country": "Paraguay",
                }
            ]
        )

        call_command(
            "import_businesses_csv",
            csv_path,
            source_name="encarnacion-test",
        )

        self.assertFalse(
            BusinessListing.objects.filter(
                source_external_id="outside-001",
            ).exists()
        )



    def test_csv_command_updates_existing_import(self):
        csv_path = self.write_csv(
            [
                {
                    "name": "Original Restaurant",
                    "industry": "restaurant",
                    "source_external_id": "update-001",
                }
            ]
        )

        call_command(
            "import_businesses_csv",
            csv_path,
            source_name="encarnacion-test",
        )

        updated_csv_path = self.write_csv(
            [
                {
                    "name": "Updated Restaurant",
                    "industry": "restaurant",
                    "source_external_id": "update-001",
                    "phone": "+595 981 123 456",
                }
            ]
        )

        call_command(
            "import_businesses_csv",
            updated_csv_path,
            source_name="encarnacion-test",
        )

        business = BusinessListing.objects.get(
            source_external_id="update-001",
        )

        self.assertEqual(
            business.name,
            "Updated Restaurant",
        )
        self.assertEqual(
            business.phone,
            "+595 981 123 456",
        )

    def test_csv_command_accepts_spanish_category(self):
        csv_path = self.write_csv(
            [
                {
                    "name": "Café Español",
                    "category": "Cafetería",
                    "source_external_id": "category-001",
                }
            ],
            fieldnames=[
                "name",
                "category",
                "source_external_id",
            ],
        )

        call_command(
            "import_businesses_csv",
            csv_path,
            source_name="encarnacion-category-test",
        )

        business = BusinessListing.objects.get(
            source_external_id="category-001",
        )

        self.assertEqual(
            business.industry,
            BusinessListing.INDUSTRY_RESTAURANT,
        )
        self.assertEqual(
            business.discovery_hub.slug,
            "restaurants",
        )

    def test_csv_command_accepts_portuguese_category(self):
        csv_path = self.write_csv(
            [
                {
                    "name": "Imóveis Paraná",
                    "category": "Imobiliária",
                    "source_external_id": "category-002",
                }
            ],
            fieldnames=[
                "name",
                "category",
                "source_external_id",
            ],
        )

        call_command(
            "import_businesses_csv",
            csv_path,
            source_name="encarnacion-category-test",
        )

        business = BusinessListing.objects.get(
            source_external_id="category-002",
        )

        self.assertEqual(
            business.industry,
            BusinessListing.INDUSTRY_REAL_ESTATE,
        )
        self.assertEqual(
            business.discovery_hub.slug,
            "real-estate",
        )

    def test_csv_command_rejects_unknown_category(self):
        csv_path = self.write_csv(
            [
                {
                    "name": "Unknown Business",
                    "category": "Tienda de tecnología",
                    "source_external_id": "category-003",
                }
            ],
            fieldnames=[
                "name",
                "category",
                "source_external_id",
            ],
        )

        with self.assertRaisesMessage(
            Exception,
            "unknown category",
        ):
            call_command(
                "import_businesses_csv",
                csv_path,
                source_name="encarnacion-category-test",
            )

class BusinessCategoryNormalizerTests(TestCase):
    def test_normalizes_case_whitespace_and_accents(self):
        self.assertEqual(
            normalize_category_key("  CAFETERÍA  "),
            "cafeteria",
        )

    def test_maps_english_restaurant_category(self):
        self.assertEqual(
            normalize_category("Coffee Shop"),
            BusinessListing.INDUSTRY_RESTAURANT,
        )

    def test_maps_spanish_restaurant_category(self):
        self.assertEqual(
            normalize_category("Churrasquería"),
            BusinessListing.INDUSTRY_RESTAURANT,
        )

    def test_maps_spanish_law_category(self):
        self.assertEqual(
            normalize_category("Estudio Jurídico"),
            BusinessListing.INDUSTRY_LAW_FIRM,
        )

    def test_maps_portuguese_law_category(self):
        self.assertEqual(
            normalize_category("Escritório de Advocacia"),
            BusinessListing.INDUSTRY_LAW_FIRM,
        )

    def test_maps_spanish_real_estate_category(self):
        self.assertEqual(
            normalize_category("Inmobiliaria"),
            BusinessListing.INDUSTRY_REAL_ESTATE,
        )

    def test_maps_portuguese_real_estate_category(self):
        self.assertEqual(
            normalize_category("Corretor de Imóveis"),
            BusinessListing.INDUSTRY_REAL_ESTATE,
        )

    def test_unknown_category_returns_none(self):
        self.assertIsNone(
            normalize_category("Tienda de tecnología")
        )
