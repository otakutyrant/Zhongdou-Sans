#!/usr/bin/env python3
# pyright: basic, reportAttributeAccessIssue=false
"""Validate that a release tag agrees with the built font metadata."""

import argparse
import re
from pathlib import Path

from fontTools.ttLib import TTFont


def validate_release(tag: str, font_path: Path) -> None:
    """Require *tag* and the release metadata in *font_path* to agree."""
    match = re.fullmatch(r"v(\d+\.\d{3})", tag)
    if match is None:
        raise ValueError("release tags must have the form v3.000")
    version = match.group(1)

    font = TTFont(font_path)
    # OpenType stores fontRevision as a 16.16 fixed-point number, so most
    # three-decimal versions acquire a tiny, unavoidable quantization error.
    revision = font["head"].fontRevision
    if abs(revision - float(version)) > 1 / 65536:
        raise ValueError(f"head.fontRevision is {revision}, expected {version}")

    names = font["name"].names
    unique_ids = {record.toUnicode() for record in names if record.nameID == 3}
    version_names = {record.toUnicode() for record in names if record.nameID == 5}
    families = {record.toUnicode() for record in names if record.nameID == 16}
    if not unique_ids or any(not value.startswith(f"{version};") for value in unique_ids):
        raise ValueError(f"unique font identifiers do not use version {version}")
    if version_names != {f"Version {version}"}:
        raise ValueError(f"unexpected version name records: {sorted(version_names)}")
    if families != {"Zhongdou Sans"}:
        raise ValueError(f"unexpected typographic family names: {sorted(families)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    parser.add_argument("font", type=Path)
    args = parser.parse_args()
    validate_release(args.tag, args.font)


if __name__ == "__main__":
    main()
