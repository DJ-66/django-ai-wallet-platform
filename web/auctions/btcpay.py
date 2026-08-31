from decimal import Decimal

import requests
from django.conf import settings


class BTCPayError(RuntimeError):
    pass


def _config():
    url = settings.BTCPAY_URL
    store_id = settings.BTCPAY_STORE_ID
    api_key = settings.BTCPAY_API_KEY

    missing = [
        name
        for name, value in (
            ("BTCPAY_URL", url),
            ("BTCPAY_STORE_ID", store_id),
            ("BTCPAY_API_KEY", api_key),
        )
        if not value
    ]

    if missing:
        raise BTCPayError(
            "Missing BTCPay configuration: " + ", ".join(missing)
        )

    return url, store_id, api_key


def _headers():
    _, _, api_key = _config()
    return {
        "Authorization": f"token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(method, path, **kwargs):
    url, _, _ = _config()

    try:
        response = requests.request(
            method,
            f"{url}{path}",
            headers=_headers(),
            timeout=settings.BTCPAY_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        status = getattr(exc.response, "status_code", None)
        if status:
            raise BTCPayError(
                f"BTCPay request failed with HTTP {status}"
            ) from exc
        raise BTCPayError("BTCPay request failed") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise BTCPayError("BTCPay returned invalid JSON") from exc


def get_store():
    _, store_id, _ = _config()
    return _request("GET", f"/api/v1/stores/{store_id}")


def get_invoice(invoice_id):
    _, store_id, _ = _config()
    return _request(
        "GET",
        f"/api/v1/stores/{store_id}/invoices/{invoice_id}",
    )


def create_invoice(
    *,
    amount,
    currency="USD",
    metadata=None,
    checkout=None,
):
    _, store_id, _ = _config()

    decimal_amount = Decimal(str(amount))

    if decimal_amount <= 0:
        raise ValueError("Invoice amount must be greater than zero.")

    payload = {
        "amount": format(decimal_amount, "f"),
        "currency": currency,
    }

    if metadata:
        payload["metadata"] = metadata

    if checkout:
        payload["checkout"] = checkout

    return _request(
        "POST",
        f"/api/v1/stores/{store_id}/invoices",
        json=payload,
    )


def create_payment_intent_invoice(payment_intent):
    from django.db import transaction

    from .models import PaymentIntent

    if not isinstance(payment_intent, PaymentIntent):
        raise TypeError("payment_intent must be a PaymentIntent")

    if (
        payment_intent.settlement_source
        != PaymentIntent.SETTLEMENT_BTCPAY
    ):
        raise BTCPayError(
            "PaymentIntent is not configured "
            "for BTCPay settlement."
        )

    with transaction.atomic():
        locked = (
            PaymentIntent.objects
            .select_for_update()
            .get(pk=payment_intent.pk)
        )

        if locked.btcpay_invoice_id:
            return locked

        invoice = create_invoice(
            amount=locked.amount,
            currency=locked.currency,
            metadata={
                "payment_intent_id": locked.pk,
                "purpose": locked.purpose,
                "source": "FANZ",
            },
        )

        invoice_id = invoice.get("id")
        checkout_link = invoice.get("checkoutLink", "")

        if not invoice_id:
            raise BTCPayError(
                "BTCPay invoice response did not include an invoice id"
            )

        locked.btcpay_invoice_id = invoice_id
        locked.btcpay_checkout_link = checkout_link
        locked.status = "invoice_created"

        locked.save(
            update_fields=[
                "btcpay_invoice_id",
                "btcpay_checkout_link",
                "status",
                "updated_at",
            ]
        )

        return locked
