from django.http import HttpResponseRedirect


class Fanz404RedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (
            response.status_code == 404
            and request.path != "/auctions/tag/404/"
            and request.method in ("GET", "HEAD")
        ):
            return HttpResponseRedirect(
                "https://fanz.to/auctions/tag/404/"
            )

        return response
