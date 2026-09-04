#!/usr/bin/env python3

import argparse
import base64
import hashlib
import json
from pathlib import Path


DEPENDENCY_IDS = [
    "0x0000000000000000000000000000000000000000000000000000000000000001",
    "0x0000000000000000000000000000000000000000000000000000000000000002",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "package_dir",
        help="Generated creator package directory.",
    )

    parser.add_argument(
        "--publication-key",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Destination JSON file.",
    )

    parser.add_argument(
        "--network",
        required=True,
        choices=("testnet", "mainnet"),
    )

    parser.add_argument(
        "--recipient-address",
        required=True,
        help=(
            "Creator-provided canonical Sui address "
            "for creator-owned publication assets."
        ),
    )

    args = parser.parse_args()

    recipient_address = (
        args.recipient_address
        .strip()
        .lower()
    )

    import re

    if not re.fullmatch(
        r"0x[0-9a-f]{64}",
        recipient_address,
    ):
        raise SystemExit(
            "Recipient address must be a canonical "
            "32-byte lowercase Sui address."
        )

    package_dir = Path(args.package_dir).resolve()

    if not package_dir.is_dir():
        raise SystemExit(
            f"Package directory not found: {package_dir}"
        )

    package_name = package_dir.name

    sources_dir = package_dir / "sources"
    move_files = sorted(sources_dir.glob("*.move"))

    if len(move_files) != 1:
        raise SystemExit(
            "Creator package must contain exactly one Move source file."
        )

    source_path = move_files[0]
    module_name = source_path.stem
    coin_struct_name = module_name.upper()

    module_path = (
        package_dir
        / "build"
        / package_name
        / "bytecode_modules"
        / f"{module_name}.mv"
    )

    if not module_path.is_file():
        raise SystemExit(
            "Compiled creator module not found: "
            f"{module_path}"
        )

    source_bytes = source_path.read_bytes()
    module_bytes = module_path.read_bytes()

    payload = {
        "publication_key": args.publication_key,
        "chain": "sui",
        "network": args.network,
        "recipient_address": recipient_address,
        "module_name": module_name,
        "coin_struct_name": coin_struct_name,
        "source_sha256": sha256_bytes(source_bytes),
        "artifact_sha256": sha256_bytes(module_bytes),
        "modules": [
            base64.b64encode(
                module_bytes
            ).decode("ascii")
        ],
        "dependency_ids": DEPENDENCY_IDS,
    }

    output_path = Path(args.output).resolve()

    output_path.write_text(
        json.dumps(
            payload,
            separators=(",", ":"),
        )
        + "\n"
    )

    print(
        f"publication_key={payload['publication_key']}"
    )
    print(
        f"module_name={payload['module_name']}"
    )
    print(
        f"coin_struct_name={payload['coin_struct_name']}"
    )
    print(
        f"source_sha256={payload['source_sha256']}"
    )
    print(
        f"artifact_sha256={payload['artifact_sha256']}"
    )
    print(
        f"module_bytes={len(module_bytes)}"
    )
    print(
        f"output={output_path}"
    )


if __name__ == "__main__":
    main()
