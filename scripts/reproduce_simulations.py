from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNROOT = ROOT / "reproduction_runs/simulation"

SPECS = {
    "p1b1": {
        "code": ROOT / "src/simulation/p1_portability_simulation_b1.py",
        "out": RUNROOT / "p1b1_full",
        "args": [
            "--mode", "full",
            "--reps", "1000",
            "--stress-reps", "500",
            "--workers", "4",
            "--bootstrap-draws", "2000",
            "--epsilon", "0.005",
            "--seed-base", "202608271",
        ],
    },
    "p1c": {
        "code": ROOT / "src/simulation/p1c_rare_binary_simulation.py",
        "out": RUNROOT / "p1c_full",
        "args": [
            "--mode", "full",
            "--reps", "500",
            "--stress-reps", "300",
            "--workers", "4",
            "--bootstrap-draws", "1500",
            "--epsilon", "0.005",
            "--seed-base", "202608272",
        ],
    },
}

def run(name):
    spec = SPECS[name]
    spec["out"].mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(spec["code"]),
        "--outdir", str(spec["out"]),
        *spec["args"],
    ]
    print("\n==", name, "==")
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["p1b1", "p1c", "all"], default="all")
    args = ap.parse_args()
    names = ["p1b1", "p1c"] if args.which == "all" else [args.which]
    for name in names:
        run(name)
    print("\nSimulation reproduction completed.")

if __name__ == "__main__":
    main()
