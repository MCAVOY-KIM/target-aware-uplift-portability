from pathlib import Path
import argparse
import hashlib

EXPECTED_SHA256 = "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data",
        default="data/raw/criteo-research-uplift-v2.1.csv.gz",
        help="Path to CRITEO-UPLIFT v2.1 gzip CSV.",
    )
    args = ap.parse_args()
    path = Path(args.data).resolve()
    if not path.is_file():
        raise SystemExit(f"Raw data not found: {path}")
    got = sha256(path)
    print("file:", path)
    print("sha256:", got)
    if got != EXPECTED_SHA256:
        raise SystemExit(
            f"SHA-256 mismatch. expected={EXPECTED_SHA256} got={got}"
        )
    print("Raw-data checksum: PASS")

if __name__ == "__main__":
    main()
