#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SUI_ROOT = REPO_ROOT / "sui"
TOOLS_ROOT = SUI_ROOT / "tools"
GENERATED_ROOT = SUI_ROOT / "generated"


def run(command):
    print(
        "+ " + " ".join(str(part) for part in command),
        flush=True,
    )

    subprocess.run(
        [str(part) for part in command],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate, policy-check, build, and prepare "
            "a FANZ Founder creator-coin publication."
        )
    )

    parser.add_argument(
        "--handle",
        required=True,
    )

    parser.add_argument(
        "--symbol",
        required=True,
    )

    parser.add_argument(
        "--name",
        required=True,
    )

    parser.add_argument(
        "--publication-key",
        required=True,
    )

    parser.add_argument(
        "--recipient-address",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    parser.add_argument(
        "--description",
        default=(
            "Fixed-supply FANZ creator economy coin"
        ),
    )

    parser.add_argument(
        "--icon-url",
        default="",
    )

    args = parser.parse_args()

    handle = (
        args.handle
        .strip()
        .lower()
        .lstrip("@")
    )

    if not handle:
        raise SystemExit(
            "Founder handle cannot be empty."
        )

    package_name = (
        f"fanz_creator_{handle}"
    )

    package_dir = (
        GENERATED_ROOT / package_name
    )

    generator = (
        TOOLS_ROOT /
        "generate_creator_coin.py"
    )

    validator = (
        TOOLS_ROOT /
        "validate_creator_coin.py"
    )

    publication_builder = (
        TOOLS_ROOT /
        "build_creator_publication.py"
    )

    run([
        sys.executable,
        generator,
        "--handle",
        handle,
        "--symbol",
        args.symbol,
        "--name",
        args.name,
        "--description",
        args.description,
        "--icon-url",
        args.icon_url,
        "--recipient-address",
        args.recipient_address,
    ])

    run([
        sys.executable,
        validator,
        package_dir,
    ])

    run([
        "docker",
        "run",
        "--rm",
        "--tmpfs",
        "/root:rw,nosuid,nodev,noexec,mode=700",
        "-v",
        f"{REPO_ROOT}:/work",
        "-w",
        "/work",
        "mysten/sui-tools:mainnet",
        "sh",
        "-lc",
        (
            "if ! sui move build "
            "--path "
            f"sui/generated/{package_name} "
            "--dump-bytecode-as-base64 "
            "--no-tree-shaking "
            ">/tmp/sui-build.log 2>&1; then "
            "sed -E "
            "'s/(secret recovery phrase[[:space:]]*:[[:space:]]*).*/"
            "\\1[REDACTED]/' "
            "/tmp/sui-build.log >&2; "
            "exit 1; "
            "fi"
        ),
    ])

    run([
        "docker",
        "run",
        "--rm",
        "-v",
        f"{REPO_ROOT}:/work",
        "alpine:latest",
        "chown",
        "-R",
        f"{os.getuid()}:{os.getgid()}",
        (
            f"/work/sui/generated/"
            f"{package_name}"
        ),
    ])

    output_path = Path(
        args.output
    ).resolve()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    run([
        sys.executable,
        publication_builder,
        package_dir,
        "--publication-key",
        args.publication_key,
        "--recipient-address",
        args.recipient_address,
        "--output",
        output_path,
    ])

    print()
    print("founder_coin_prepare=PASS")
    print(f"handle=@{handle}")
    print(f"package_name={package_name}")
    print(f"package_dir={package_dir}")
    print(
        f"publication_key="
        f"{args.publication_key}"
    )
    print(
        f"publication_payload="
        f"{output_path}"
    )


if __name__ == "__main__":
    main()
