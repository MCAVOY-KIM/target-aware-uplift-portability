> **Public-release note:** This is an archival stage note. Author-specific local paths were replaced with `<PROJECT_ROOT>`; use the repository-root reproduction commands in `docs/reproducibility.md` for current execution.

# Target-Aware Portability — Criteo R0

Place this folder at:

`<PROJECT_ROOT>\Target_Aware_Portability_Criteo_R0`

The raw Criteo file should already be at:

`<PROJECT_ROOT>\02_data\raw\criteo-research-uplift-v2.1.csv.gz`

## Verify

```powershell
cd "<PROJECT_ROOT>"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R0\03_src\criteo_r0_audit.py"
Test-Path ".\Target_Aware_Portability_Criteo_R0\scripts\run_criteo_r0_audit.ps1"
```

All four should be `True`.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R0\scripts\run_criteo_r0_audit.ps1
```

The script streams the ~14M-row gzip file and may take several minutes.

It does not fit uplift models.

## Send back

Please send:
1. the complete console output;
2. ZIP of `05_outputs\criteo_r0_audit`.

After forensic review, R1 population construction and model-fitting code will be frozen.
