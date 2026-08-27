#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path


EXPECTED_SUPPLY = "21_000_000_000_000_000"
EXPECTED_DECIMALS = "6"


class ValidationError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def count(pattern, text):
    return len(re.findall(pattern, text, flags=re.MULTILINE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package_dir")
    args = parser.parse_args()

    package_dir = Path(args.package_dir)

    require(
        package_dir.is_dir(),
        f"Package directory not found: {package_dir}",
    )

    sources_dir = package_dir / "sources"

    move_files = sorted(sources_dir.glob("*.move"))

    require(
        len(move_files) == 1,
        "Creator package must contain exactly one Move source module.",
    )

    source_path = move_files[0]
    text = source_path.read_text()

    # ---------------------------------------------------------
    # Fixed economic constants
    # ---------------------------------------------------------

    require(
        re.search(
            rf"const\s+GENESIS_SUPPLY_BASE_UNITS\s*:\s*u64\s*=\s*{EXPECTED_SUPPLY}\s*;",
            text,
        ),
        "Genesis supply is not exactly 21,000,000,000,000,000 base units.",
    )

    require(
        re.search(
            rf"const\s+DECIMALS\s*:\s*u8\s*=\s*{EXPECTED_DECIMALS}\s*;",
            text,
        ),
        "Decimals are not exactly 6.",
    )

    # ---------------------------------------------------------
    # Genesis mint policy
    # ---------------------------------------------------------

    require(
        count(r"\btreasury_cap\.mint\s*\(", text) == 1,
        "Creator coin must contain exactly one TreasuryCap mint call.",
    )

    require(
        count(
            r"\bcurrency\.make_supply_fixed\s*\(",
            text,
        ) == 1,
        "Creator coin must contain exactly one make_supply_fixed call.",
    )

    require(
        count(
            r"\bcurrency\.make_supply_burn_only\s*\(",
            text,
        ) == 0,
        "Burn-only supply policy is forbidden.",
    )

    # ---------------------------------------------------------
    # Public API restrictions
    # ---------------------------------------------------------

    public_functions = re.findall(
        r"public(?:\s+entry)?\s+fun\s+([A-Za-z0-9_]+)",
        text,
    )

    allowed_public = {
        "decimals",
        "genesis_supply_base_units",
        "version",
    }

    unexpected = sorted(
        set(public_functions) - allowed_public
    )

    require(
        not unexpected,
        "Unexpected public functions: "
        + ", ".join(unexpected),
    )

    require(
        "mint" not in public_functions,
        "Public mint function is forbidden.",
    )

    # ---------------------------------------------------------
    # TreasuryCap must not escape init()
    # ---------------------------------------------------------

    require(
        count(r"\bTreasuryCap\b", text) <= 4,
        "Unexpected TreasuryCap references detected.",
    )

    require(
        not re.search(
            r"public(?:\s+entry)?\s+fun[\s\S]{0,300}\bTreasuryCap\b",
            text,
        ),
        "Public function may not accept or expose TreasuryCap.",
    )

    # ---------------------------------------------------------
    # OTW structure sanity
    # ---------------------------------------------------------

    module_match = re.search(
        r"module\s+[A-Za-z0-9_]+::([A-Za-z0-9_]+)",
        text,
    )

    require(
        module_match,
        "Move module declaration not found.",
    )

    module_name = module_match.group(1)
    expected_otw = module_name.upper()

    require(
        re.search(
            rf"public\s+struct\s+{re.escape(expected_otw)}\s+has\s+drop\s*\{{\s*\}}",
            text,
        ),
        f"Expected one-time witness struct {expected_otw}.",
    )

    # ---------------------------------------------------------
    # Required lifecycle calls
    # ---------------------------------------------------------

    require(
        "new_currency_with_otw" in text,
        "Currency must be created with new_currency_with_otw.",
    )

    require(
        "currency.finalize(ctx)" in text,
        "Metadata capability must be finalized explicitly.",
    )

    print("creator_coin_policy=PASS")
    print(f"source={source_path}")
    print(f"supply_base_units={EXPECTED_SUPPLY}")
    print(f"decimals={EXPECTED_DECIMALS}")
    print(f"otw={expected_otw}")
    print(
        "public_functions="
        + ",".join(sorted(public_functions))
    )


if __name__ == "__main__":
    try:
        main()
    except ValidationError as exc:
        print(
            f"creator_coin_policy=FAIL: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
