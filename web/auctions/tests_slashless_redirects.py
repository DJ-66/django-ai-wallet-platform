"""WP03.4 middleware regression tests."""

from django.conf import settings
from django.http import HttpResponse
from django.middleware.common import CommonMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import is_valid_path
from core.fanz_404_redirect import Fanz404RedirectMiddleware


@override_settings(DEBUG=False, APPEND_SLASH=True,
                   PREPEND_WWW=False, ALLOWED_HOSTS=["testserver"])
class SlashlessRedirectTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def response(self, request, status=404):
        classes = {
            "django.middleware.common.CommonMiddleware": CommonMiddleware,
            "core.fanz_404_redirect.Fanz404RedirectMiddleware":
                Fanz404RedirectMiddleware,
        }
        handler = lambda request: HttpResponse(status=status)
        for name in reversed(settings.MIDDLEWARE):
            if name in classes:
                handler = classes[name](handler)
        return handler(request)

    def test_slashless_routes(self):
        for path in (
            "/Fanz", "/mia", "/dj", "/auctions",
            "/auctions/feed", "/auctions/founder/tienda",
        ):
            self.assertFalse(is_valid_path(path))
            self.assertTrue(is_valid_path(path + "/"))
            for method in ("get", "head"):
                with self.subTest(path=path, method=method):
                    r = self.response(getattr(self.factory, method)(path))
                    self.assertEqual(r.status_code, 301)
                    self.assertEqual(r["Location"], path + "/")

    def test_query_preserved(self):
        path = "/auctions/founder/tienda"
        query = "lang=pt&source=SunsetCam&ref=a%2Fb"
        for method in ("get", "head"):
            r = self.response(getattr(self.factory, method)(path + "?" + query))
            self.assertEqual(r.status_code, 301)
            self.assertEqual(r["Location"], path + "/?" + query)

    def test_missing_route(self):
        path = "/auctions/nonexistent/deep/path"
        for method in ("get", "head"):
            r = self.response(getattr(self.factory, method)(path))
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r["Location"], "https://fanz.to/auctions/tag/404/")

    def test_no_redirect_loop(self):
        r = self.response(self.factory.get("/auctions/tag/404/"))
        self.assertEqual(r.status_code, 404)
        self.assertFalse(r.has_header("Location"))

    def test_missing_write_requests(self):
        for method in ("post", "put", "patch", "delete"):
            r = self.response(getattr(self.factory, method)(
                "/auctions/nonexistent/deep/path/"))
            self.assertEqual(r.status_code, 404)
            self.assertFalse(r.has_header("Location"))

    def test_existing_responses(self):
        for status in (200, 302, 400, 401, 403, 405, 500):
            r = self.response(self.factory.get(
                "/auctions/founder/tienda/"), status)
            self.assertEqual(r.status_code, status)
