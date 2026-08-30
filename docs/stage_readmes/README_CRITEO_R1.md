> **Public-release note:** This is an archival stage note. Author-specific local paths were replaced with `<PROJECT_ROOT>`; use the repository-root reproduction commands in `docs/reproducibility.md` for current execution.

# Target-Aware Portability — Criteo R1

Place at:

`<PROJECT_ROOT>\Target_Aware_Portability_Criteo_R1`

Keep R0 and R0.1 outputs unchanged.

## Verify

```powershell
cd "<PROJECT_ROOT>"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R0\05_outputs\criteo_r0_audit"
Test-Path ".\Target_Aware_Portability_Criteo_R01\05_outputs\criteo_r01_shift_materialization"
Test-Path ".\Target_Aware_Portability_Criteo_R1\03_src\criteo_r1_population_models.py"
Test-Path ".\Target_Aware_Portability_Criteo_R1\scripts\run_criteo_r1.ps1"
```

All six should be True.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R1\scripts\run_criteo_r1.ps1
```

R1 reads the raw gzip several times and trains six models for each of the three frozen source/target scenarios. This is the first computationally heavy real-data stage.

No target treatment/outcome is used.

## Send back

Send:
1. complete console output;
2. ZIP of `05_outputs\criteo_r1`.

The ZIP contains model artifacts, so it may be larger than prior result ZIPs.

After forensic review and PASS, the fitted model library and budget-specific source winners are frozen. Then R2 will use target X plus source_infer outcomes for the actual portability assessment, while target outcomes remain hidden.
