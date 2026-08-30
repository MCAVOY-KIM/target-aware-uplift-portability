from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/criteo"

ORDER = ["r0", "r01", "r1", "r11", "r12", "r1f", "r2", "r3"]

def run(cmd, stage):
    print(f"\n== {stage} ==")
    print("Running:", " ".join(str(x) for x in cmd))
    subprocess.run([str(x) for x in cmd], check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data",
        default="data/raw/criteo-research-uplift-v2.1.csv.gz",
    )
    ap.add_argument(
        "--out-root",
        default="reproduction_runs/criteo",
    )
    ap.add_argument("--chunksize", type=int, default=500000)
    ap.add_argument("--through", choices=ORDER, default="r2")
    args = ap.parse_args()

    data = Path(args.data).resolve()
    if not data.is_file():
        raise SystemExit(f"Raw data not found: {data}")

    out = Path(args.out_root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    chunk = str(args.chunksize)

    r0 = out / "r0"
    r01 = out / "r01"
    r1 = out / "r1"
    r11 = out / "r11"
    r12 = out / "r12"
    r1f = out / "r1f"
    r2 = out / "r2"
    r3 = out / "r3"

    commands = {
        "r0": [
            py, SRC/"criteo_r0_audit.py",
            "--data", data, "--outdir", r0, "--chunksize", chunk,
        ],
        "r01": [
            py, SRC/"criteo_r01_shift_materialization.py",
            "--data", data, "--r0-outdir", r0, "--outdir", r01,
            "--chunksize", chunk,
        ],
        "r1": [
            py, SRC/"criteo_r1_population_models.py",
            "--data", data, "--r0-outdir", r0, "--r01-outdir", r01,
            "--outdir", r1, "--chunksize", chunk,
        ],
        "r11": [
            py, SRC/"criteo_r11_budget_randomization_audit.py",
            "--data", data, "--r0-outdir", r0, "--r01-outdir", r01,
            "--r1-source", SRC/"criteo_r1_population_models.py",
            "--r1-outdir", r1, "--outdir", r11, "--chunksize", chunk,
        ],
        "r12": [
            py, SRC/"criteo_r12_propensity_adjustment.py",
            "--data", data, "--r0-outdir", r0, "--r01-outdir", r01,
            "--r1-source", SRC/"criteo_r1_population_models.py",
            "--r11-source", SRC/"criteo_r11_budget_randomization_audit.py",
            "--r1-outdir", r1, "--r11-outdir", r11,
            "--outdir", r12, "--chunksize", chunk,
        ],
        "r1f": [
            py, SRC/"criteo_r1f_finalization.py",
            "--data", data, "--r0-outdir", r0, "--r01-outdir", r01,
            "--r1-source", SRC/"criteo_r1_population_models.py",
            "--r12-source", SRC/"criteo_r12_propensity_adjustment.py",
            "--r1-outdir", r1, "--r12-outdir", r12,
            "--outdir", r1f, "--chunksize", chunk,
        ],
        "r2": [
            py, SRC/"criteo_r2_portability.py",
            "--data", data, "--r0-outdir", r0, "--r01-outdir", r01,
            "--r1-source", SRC/"criteo_r1_population_models.py",
            "--r1-outdir", r1, "--r12-outdir", r12,
            "--r1f-outdir", r1f, "--outdir", r2, "--chunksize", chunk,
        ],
        "r3": [
            py, SRC/"criteo_r3_target_benchmark.py",
            "--data", data, "--r0-outdir", r0, "--r01-outdir", r01,
            "--r1-source", SRC/"criteo_r1_population_models.py",
            "--r1-outdir", r1, "--r2-outdir", r2,
            "--outdir", r3, "--chunksize", chunk,
        ],
    }

    last = ORDER.index(args.through)
    for stage in ORDER[:last + 1]:
        run(commands[stage], stage)

    print("\nCriteo recomputation completed through", args.through)
    if args.through == "r2":
        print(
            "R2 is target-outcome blind. R3 is intentionally separate and "
            "will verify frozen R2 byte hashes before the target-outcome unlock."
        )

if __name__ == "__main__":
    main()
