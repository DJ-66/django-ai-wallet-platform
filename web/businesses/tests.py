from django.contrib.auth import get_user_model
from django.test import TestCase

from .import_services import (
    BusinessImportRecord,
    BusinessImportValidationError,
    import_business_record,
    import_business_records,
    normalize_business_record,
)
from .models import BusinessListing


class BusinessImportServiceTests(TestCase):
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
