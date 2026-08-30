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

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check(path: Path, expected: str, label: str):
    if not path.is_file():
        raise RuntimeError(f"Missing {label}: {path}")
    got = sha(path)
    if got != expected:
        raise RuntimeError(
            f"Hash mismatch for {label}: expected={expected} got={got}"
        )

def main():
    # Verify every imported frozen source if the complete manifest exists.
    manifest = ROOT / "provenance/checksums/source_sha256_complete.csv"
    if manifest.is_file():
        with manifest.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                check(ROOT / row["repository_path"], row["sha256"], row["repository_path"])
        print("Frozen source manifest: PASS")
    else:
        print("Frozen source manifest: SKIPPED (manifest not found)")

    for rel, expected in R4_EXPECTED.items():
        check(ROOT / rel, expected, rel)
    print("R2/R3 frozen evidence hash chain: PASS")

    r11 = ROOT / "src/criteo/criteo_r11_budget_randomization_audit.py"
    expected_r11 = "fa011f1d63e0394174e73e48989ad4b80882827c1c6c990b61fe4bbd29e3176e"
    check(r11, expected_r11, "R11 frozen source")
    print("R11 dependency hash: PASS")
    print("Frozen repository verification: PASS")

if __name__ == "__main__":
    main()
