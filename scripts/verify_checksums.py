#!/usr/bin/env python3
"""Verify locally available artifacts against provenance/artifact_manifest.csv.

Missing files are reported as MISSING rather than treated as hash failures so that
external/non-redistributed artifacts can still be listed in the manifest.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "provenance" / "artifact_manifest.csv"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    if not MANIFEST.exists():
        print(f"Manifest not found: {MANIFEST}", file=sys.stderr)
        return 2

    failures = 0
    checked = 0
    missing = 0

    with MANIFEST.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        rel = (row.get("local_path") or "").strip()
        expected = (row.get("sha256") or "").strip().lower()
        artifact = (row.get("artifact") or rel or "unnamed").strip()

        if not rel or not expected:
            print(f"SKIP    {artifact}: path/hash not finalized")
            continue

        path = ROOT / rel
        if not path.exists():
            missing += 1
            print(f"MISSING {artifact}: {rel}")
            continue

        actual = sha256_file(path)
        checked += 1
        if actual == expected:
            print(f"PASS    {artifact}: {actual}")
        else:
            failures += 1
            print(f"FAIL    {artifact}\n        expected={expected}\n        actual  ={actual}")

    print(f"\nSummary: checked={checked}, missing={missing}, hash_failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
