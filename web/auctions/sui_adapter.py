import requests
from django.conf import settings


class SuiAdapterError(RuntimeError):
    pass


class SuiAdapterConflict(SuiAdapterError):
    pass


def _config():
    url = settings.FANZ_SUI_URL
    api_token = settings.FANZ_SUI_API_TOKEN

    missing = [
        name
        for name, value in (
            ("FANZ_SUI_URL", url),
            ("FANZ_SUI_API_TOKEN", api_token),
        )
        if not value
    ]

    if missing:
        raise SuiAdapterError(
            "Missing FANZ Sui configuration: " + ", ".join(missing)
        )

    return url, api_token


def _headers():
    _, api_token = _config()

    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(method, path, **kwargs):
    url, _ = _config()

    try:
        response = requests.request(
            method,
            f"{url}{path}",
            headers=_headers(),
            timeout=settings.FANZ_SUI_TIMEOUT,
            **kwargs,
        )

        if response.status_code == 409:
            raise SuiAdapterConflict(
                "FANZ Sui rejected conflicting submission data."
            )

        response.raise_for_status()

    except SuiAdapterConflict:
        raise
    except requests.RequestException as exc:
        status = getattr(exc.response, "status_code", None)

        if status:
            raise SuiAdapterError(
                f"FANZ Sui request failed with HTTP {status}"
            ) from exc

        raise SuiAdapterError(
            "FANZ Sui request failed"
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise SuiAdapterError(
            "FANZ Sui returned invalid JSON"
        ) from exc


def prepare_delivery(delivery):
    asset = delivery.asset

    if not asset.coin_type:
        raise SuiAdapterError(
            "EconomyAsset has no on-chain coin_type."
        )

    payload = {
        "submission_key": str(delivery.submission_key),
        "chain": asset.chain,
        "coin_type": asset.coin_type,
        "recipient_address": delivery.recipient_address,
        "amount_base_units": str(delivery.amount_base_units),
    }

    return _request(
        "POST",
        "/v1/deliveries",
        json=payload,
    )


def get_delivery(submission_key):
    return _request(
        "GET",
        f"/v1/deliveries/{submission_key}",
    )
