from io import BytesIO
from urllib.parse import urlparse

import qrcode
from django.http import HttpResponse, HttpResponseBadRequest


def current_page_qr(request):
    target_url = request.GET.get("url", "").strip()

    if not target_url:
        return HttpResponseBadRequest("Missing URL.")

    if len(target_url) > 2048:
        return HttpResponseBadRequest("URL is too long.")

    parsed_url = urlparse(target_url)

    if parsed_url.scheme not in {"http", "https"}:
        return HttpResponseBadRequest("Invalid URL scheme.")

    request_host = request.get_host().split(":")[0].lower()
    target_host = (parsed_url.hostname or "").lower()

    if target_host != request_host:
        return HttpResponseBadRequest("External URLs are not allowed.")

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )

    qr.add_data(target_url)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="image/png",
    )
    response["Cache-Control"] = "no-store"

    return response
