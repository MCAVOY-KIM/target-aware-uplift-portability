from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "src/criteo/criteo_r4_evidence_freeze.py"
R2 = ROOT / "outputs/criteo/r2"
R3 = ROOT / "outputs/criteo/r3"
OUT = ROOT / "reproduction_runs/r4_frozen_audit"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(CODE),
        "--r2-outdir", str(R2),
        "--r3-outdir", str(R3),
        "--outdir", str(OUT),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("Frozen R4 evidence synthesis: PASS")
    print("Output:", OUT)

if __name__ == "__main__":
    main()
