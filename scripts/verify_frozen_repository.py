from pathlib import Path
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[1]

R4_EXPECTED = {
    "outputs/criteo/r2/criteo_r2_pairwise_contrasts.csv":
        "5949d500efbc74a0fe033f81eb47ed6374f158c378b64d453ffa240c398b7a23",
    "outputs/criteo/r2/criteo_r2_portability_bounds.csv":
        "674ffed3be874de1fb6c76f376d6d726288dc9eaefdeb4e99d656888dcd3cbba",
    "outputs/criteo/r2/criteo_r2_tolerance_frontier.csv":
        "26f75b46c669d85620f35034d3d5ddbf9ead50a36df47e0948f79e4c2d21c479",
    "outputs/criteo/r2/criteo_r2_ratio_inference_audit.csv":
        "2b01c556a943ce9fecdde1a7543b60c1aa78840f61fd6196cb04b0587e38138a",
    "outputs/criteo/r3/criteo_r3_regret_benchmark.csv":
        "599628ec5ae6bb1256d3a0a721dae0facdee7f54fef0847f67b3def6128dbbde",
    "outputs/criteo/r3/criteo_r3_target_pairwise_benchmark.csv":
        "d854ba2fec73aeebac5a72abb623bd7294aa199be643dcdfbc7442fcf7e1b653",
    "outputs/criteo/r3/criteo_r3_target_benchmark_gains.csv":
        "0ca905d88d1020036c354d30d8a28067d00f64e206172fffda839c8d321b1fc8",
    "outputs/criteo/r3/criteo_r3_tolerance_benchmark.csv":
        "cce8d38a404c34cbf5b1121b6f67e9b9d53b9128b40374bfb97b82f736c1f8df",
    "outputs/criteo/r3/criteo_r3_target_nuisance_audit.csv":
        "cc8632961d61732de7bba09c5486ea861ce59570aa247c113ed26eadd3125053",
    "outputs/criteo/r3/criteo_r3_gate.csv":
        "2dce7faa555bc15ab565835289276ef02e8e1190514cd3fcf77df49aa5079f08",
}

def sha_raw(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sha_canonical_lf(path: Path) -> str:
    # Git may materialize text files as CRLF on Windows depending on user config.
    # Source-integrity hashes therefore use a canonical LF representation.
    data = path.read_bytes()
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()

def require_hash(path: Path, expected: str, label: str, canonical_lf=False):
    if not path.is_file():
        raise RuntimeError(f"Missing {label}: {path}")
    got = sha_canonical_lf(path) if canonical_lf else sha_raw(path)
    if got != expected:
        mode = "canonical-LF" if canonical_lf else "raw-byte"
        raise RuntimeError(
            f"Hash mismatch for {label} ({mode}): expected={expected} got={got}"
        )

def main():
    manifest = ROOT / "provenance/checksums/source_sha256_canonical_lf.csv"
    if not manifest.is_file():
        raise RuntimeError(f"Missing source-integrity manifest: {manifest}")

    with manifest.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 11:
        raise RuntimeError(f"Expected 11 frozen source records, found {len(rows)}")

    for row in rows:
        require_hash(
            ROOT / row["repository_path"],
            row["sha256_canonical_lf"],
            row["repository_path"],
            canonical_lf=True,
        )
    print(f"Frozen source canonical-LF manifest ({len(rows)} files): PASS")

    # Frozen evidence artifacts retain byte-level hashes.
    for rel, expected in R4_EXPECTED.items():
        require_hash(ROOT / rel, expected, rel, canonical_lf=False)
    print("R2/R3 frozen evidence raw-byte hash chain: PASS")

    print("Frozen repository verification: PASS")

if __name__ == "__main__":
    main()
