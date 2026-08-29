#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PREPARE_TOOL = (
    REPO_ROOT
    / "sui"
    / "tools"
    / "prepare_founder_coin_publication.py"
)

PUBLICATION_ROOT = (
    REPO_ROOT
    / "sui"
    / "prepared-publications"
)


class QueueError(RuntimeError):
    pass


def run_capture(command):
    result = subprocess.run(
        [str(part) for part in command],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return result.stdout, result.stderr


def load_pending_jobs():
    stdout, stderr = run_capture([
        "docker",
        "compose",
        "exec",
        "-T",
        "web",
        "python",
        "manage.py",
        "pending_founder_coin_publications",
    ])

    jobs = []

    for line in stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            jobs.append(
                json.loads(line)
            )
        except json.JSONDecodeError as exc:
            raise QueueError(
                "Pending Founder coin queue emitted "
                "non-JSON stdout."
            ) from exc

    return jobs, stderr.strip()


def validate_job(job):
    required = {
        "economy_asset_id",
        "founder_account_id",
        "handle",
        "name",
        "symbol",
        "generated_package",
        "publication_key",
        "recipient_address",
    }

    missing = sorted(
        required - set(job)
    )

    if missing:
        raise QueueError(
            "Pending Founder coin job is missing: "
            + ", ".join(missing)
        )

    handle = str(
        job["handle"]
    ).strip().lower().lstrip("@")

    expected_package = (
        f"fanz_creator_{handle}"
    )

    if job["generated_package"] != expected_package:
        raise QueueError(
            "Generated package mismatch: "
            f"expected {expected_package}, "
            f"got {job['generated_package']}."
        )

    if not str(
        job["recipient_address"]
    ).strip():
        raise QueueError(
            "Pending Founder coin job has no "
            "recipient address."
        )

    return handle


def prepare_job(job, *, force=False):
    handle = validate_job(job)

    PUBLICATION_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = (
        PUBLICATION_ROOT
        / f"{job['publication_key']}.json"
    )

    if output.exists() and not force:
        raise QueueError(
            "Prepared publication already exists: "
            f"{output}"
        )

    if force and output.exists():
        output.unlink()

    command = [
        sys.executable,
        PREPARE_TOOL,
        "--handle",
        handle,
        "--symbol",
        job["symbol"],
        "--name",
        job["name"],
        "--publication-key",
        job["publication_key"],
        "--output",
        output,
    ]

    print(
        "+ " + " ".join(
            str(part)
            for part in command
        ),
        flush=True,
    )

    subprocess.run(
        [str(part) for part in command],
        cwd=REPO_ROOT,
        check=True,
    )

    result = {
        "economy_asset_id":
            job["economy_asset_id"],
        "founder_account_id":
            job["founder_account_id"],
        "handle":
            handle,
        "name":
            job["name"],
        "symbol":
            job["symbol"],
        "publication_key":
            job["publication_key"],
        "generated_package":
            job["generated_package"],
        "recipient_address":
            job["recipient_address"],
        "publication_payload":
            str(output),
    }

    print()
    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Prepare one pending Founder vending "
            "creator-coin publication."
        )
    )

    parser.add_argument(
        "--asset-id",
        type=int,
        help=(
            "Prepare a specific pending EconomyAsset "
            "instead of the oldest pending job."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Replace an existing prepared publication "
            "JSON file. Generated Move package overwrite "
            "protection still applies."
        ),
    )

    args = parser.parse_args()

    jobs, queue_status = load_pending_jobs()

    if queue_status:
        print(
            queue_status,
            file=sys.stderr,
        )

    if args.asset_id is not None:
        jobs = [
            job
            for job in jobs
            if int(
                job["economy_asset_id"]
            ) == args.asset_id
        ]

        if not jobs:
            raise SystemExit(
                "No eligible pending Founder coin "
                f"draft for asset id={args.asset_id}."
            )

    if not jobs:
        print(
            "founder_coin_prepare_queue=EMPTY"
        )
        return

    job = jobs[0]

    prepare_job(
        job,
        force=args.force,
    )


if __name__ == "__main__":
    try:
        main()
    except QueueError as exc:
        print(
            f"founder_coin_prepare_queue=FAIL: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
