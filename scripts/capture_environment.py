#!/usr/bin/env python3
"""Capture the final reproduction environment for archival before submission."""

from __future__ import annotations

from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "environment"
OUT.mkdir(exist_ok=True)

info = [
    f"python={sys.version.replace(chr(10), ' ')}",
    f"executable={sys.executable}",
    f"platform={platform.platform()}",
    f"machine={platform.machine()}",
    f"processor={platform.processor()}",
]
(OUT / "python-platform.txt").write_text("\n".join(info) + "\n", encoding="utf-8")

try:
    freeze = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"],
        text=True,
        stderr=subprocess.STDOUT,
    )
except subprocess.CalledProcessError as exc:
    freeze = f"# pip freeze failed\n{exc.output}"

(OUT / "pip-freeze.txt").write_text(freeze, encoding="utf-8")
print(f"Wrote {OUT / 'python-platform.txt'}")
print(f"Wrote {OUT / 'pip-freeze.txt'}")
