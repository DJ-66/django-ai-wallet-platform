#!/usr/bin/env python3

import argparse
import base64
import json
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SUI_SERVICE_ROOT = REPO_ROOT / "deploy" / "sui-service"


class AcceptError(RuntimeError):
    pass


NODE_ACCEPT_SCRIPT = r'''
const encoded = process.argv[2];

if (!encoded) {
  throw new Error("missing publication payload");
}

const token = (
  process.env.FANZ_SUI_API_TOKEN || ""
).trim();

if (!token) {
  throw new Error(
    "FANZ_SUI_API_TOKEN is not configured"
  );
}

const payload = JSON.parse(
  Buffer.from(
    encoded,
    "base64",
  ).toString("utf8")
);

const response = await fetch(
  "http://127.0.0.1:3000/v1/creator-publications",
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  },
);

const body = await response.text();

console.log(JSON.stringify({
  http_status: response.status,
  body,
}));
'''


def load_payload(path):
    try:
        payload = json.loads(
            path.read_text()
        )
    except FileNotFoundError as exc:
        raise AcceptError(
            f"Publication payload not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise AcceptError(
            f"Invalid publication JSON: {path}"
        ) from exc

    required = {
        "publication_key",
        "chain",
        "module_name",
        "coin_struct_name",
        "source_sha256",
        "artifact_sha256",
        "modules",
        "dependency_ids",
    }

    missing = sorted(
        required - set(payload)
    )

    if missing:
        raise AcceptError(
            "Publication payload missing fields: "
            + ", ".join(missing)
        )

    return payload


def send_to_sui_service(
    payload,
    *,
    url=None,
    token=None,
):
    if url:
        if not token:
            raise AcceptError(
                "A token is required with --url."
            )

        request = Request(
            url,
            data=json.dumps(
                payload,
                separators=(",", ":"),
            ).encode("utf8"),
            headers={
                "Authorization":
                    f"Bearer {token}",
                "Content-Type":
                    "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=30,
            ) as response:
                status = response.status
                raw_body = (
                    response
                    .read()
                    .decode("utf8")
                )

        except HTTPError as exc:
            status = exc.code
            raw_body = (
                exc.read()
                .decode("utf8")
            )

        except URLError as exc:
            raise AcceptError(
                "Could not reach Sui service: "
                f"{exc.reason}"
            ) from exc

        try:
            body = json.loads(
                raw_body
            )
        except json.JSONDecodeError as exc:
            raise AcceptError(
                "Sui service returned non-JSON body."
            ) from exc

        return status, body

    encoded = base64.b64encode(
        json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf8")
    ).decode("ascii")

    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "sui",
        "node",
        "--input-type=module",
        "-",
        encoded,
    ]

    result = subprocess.run(
        command,
        cwd=SUI_SERVICE_ROOT,
        input=NODE_ACCEPT_SCRIPT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        raise AcceptError(
            "Sui service request failed:\n"
            + result.stderr.strip()
        )

    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    if not lines:
        raise AcceptError(
            "Sui service returned no response."
        )

    try:
        envelope = json.loads(
            lines[-1]
        )
    except json.JSONDecodeError as exc:
        raise AcceptError(
            "Could not parse Sui service response."
        ) from exc

    status = int(
        envelope["http_status"]
    )

    try:
        body = json.loads(
            envelope["body"]
        )
    except json.JSONDecodeError as exc:
        raise AcceptError(
            "Sui service returned non-JSON body."
        ) from exc

    return status, body


def validate_response(
    *,
    payload,
    status,
    body,
):
    if status not in {200, 201}:
        error = body.get(
            "error",
            "unknown Sui service error",
        )

        raise AcceptError(
            f"Sui service HTTP {status}: {error}"
        )

    publication = body.get(
        "publication"
    )

    if not isinstance(publication, dict):
        raise AcceptError(
            "Sui service response has no publication."
        )

    immutable = (
        "publication_key",
        "chain",
        "module_name",
        "coin_struct_name",
        "source_sha256",
        "artifact_sha256",
    )

    for field in immutable:
        if publication.get(field) != payload.get(field):
            raise AcceptError(
                f"Publication response mismatch: {field}"
            )

    state = publication.get("state")

    allowed_states = {
        "accepted",
        "prepared",
        "submitted",
        "confirmed",
    }

    if state not in allowed_states:
        raise AcceptError(
            f"Unexpected publication state: {state}"
        )

    return publication


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Accept one prepared Founder creator-coin "
            "publication into the Sui service journal. "
            "This command never prepares or submits it."
        )
    )

    parser.add_argument(
        "payload",
        help="Prepared creator publication JSON.",
    )

    parser.add_argument(
        "--url",
        help=(
            "Direct creator-publication endpoint, "
            "for isolated/test use."
        ),
    )

    parser.add_argument(
        "--token",
        help=(
            "Bearer token used with --url."
        ),
    )

    args = parser.parse_args()

    path = Path(
        args.payload
    ).resolve()

    payload = load_payload(path)

    status, body = send_to_sui_service(
        payload,
        url=args.url,
        token=args.token,
    )

    publication = validate_response(
        payload=payload,
        status=status,
        body=body,
    )

    print(
        json.dumps(
            {
                "accepted": True,
                "created": body.get("created"),
                "http_status": status,
                "publication_key":
                    publication["publication_key"],
                "state":
                    publication["state"],
                "module_name":
                    publication["module_name"],
                "coin_struct_name":
                    publication["coin_struct_name"],
                "source_sha256":
                    publication["source_sha256"],
                "artifact_sha256":
                    publication["artifact_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except AcceptError as exc:
        print(
            f"founder_publication_accept=FAIL: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
