#!/usr/bin/env python3

import argparse
import re
import shutil
from pathlib import Path


ROOT = Path("/workspace")
TEMPLATE_ROOT = ROOT / "templates" / "fanz_creator_coin"


def identifier(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]", "_", value)

    if not value:
        raise ValueError("Identifier cannot be empty")

    if value[0].isdigit():
        value = "_" + value

    return value


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--handle", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--description",
        default="Fixed-supply FANZ creator economy coin",
    )
    parser.add_argument("--icon-url", default="")

    args = parser.parse_args()

    handle = args.handle.lower().lstrip("@")

    package_name = identifier(
        f"fanz_creator_{handle}"
    ).lower()

    module_name = identifier(
        f"{handle}_fanz"
    ).lower()

    # Sui one-time witness rule:
    # the witness struct name must be the uppercase
    # form of the module name.
    #
    # Example:
    #   module: lisa_fanz
    #   OTW:    LISA_FANZ
    #   symbol: LISAFANZ
    coin_type = module_name.upper()

    output = ROOT / "generated" / package_name

    if output.exists():
        raise SystemExit(
            f"Refusing to overwrite existing package: {output}"
        )

    output.mkdir(parents=True)
    (output / "sources").mkdir()

    replacements = {
        "__PACKAGE_NAME__": package_name,
        "__MODULE_NAME__": module_name,
        "__COIN_TYPE__": coin_type,
        "__SYMBOL__": args.symbol,
        "__NAME__": args.name,
        "__DESCRIPTION__": args.description,
        "__ICON_URL__": args.icon_url,
    }

    move_toml = (
        TEMPLATE_ROOT /
        "Move.toml.template"
    ).read_text()

    source = (
        TEMPLATE_ROOT /
        "creator_coin.move.template"
    ).read_text()

    for old, new in replacements.items():
        move_toml = move_toml.replace(old, new)
        source = source.replace(old, new)

    (output / "Move.toml").write_text(move_toml)

    (
        output /
        "sources" /
        f"{module_name}.move"
    ).write_text(source)

    print(output)


if __name__ == "__main__":
    main()
