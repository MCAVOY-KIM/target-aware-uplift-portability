# Target-Aware Portability P1-C

Place this folder at:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\Target_Aware_Portability_P1_C`

Keep the previous `Target_Aware_Portability_P1_B1` folder unchanged.

The package reuses:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\.venv`

No Criteo file is needed yet.

## 1. Verify

```powershell
cd "C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\Target_Aware_Portability_P1_C\03_src\p1c_rare_binary_simulation.py"
Test-Path ".\Target_Aware_Portability_P1_C\scripts\run_p1c_smoke.ps1"
Test-Path ".\Target_Aware_Portability_P1_C\scripts\run_p1c_core_gate.ps1"
Test-Path ".\Target_Aware_Portability_P1_C\scripts\run_p1c_full_gate.ps1"
```

All five should be `True`.

## 2. Run Smoke only

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_P1_C\scripts\run_p1c_smoke.ps1
```

Output:

`Target_Aware_Portability_P1_C\05_outputs\p1c_smoke`

Smoke is only a technical check. Do not interpret 20-repetition coverage rates as scientific evidence.

## 3. Core — do not run yet

After Smoke review:

```powershell
.\Target_Aware_Portability_P1_C\scripts\run_p1c_core_gate.ps1
```

Core = 2,400 replications.

## 4. Full — do not run yet

Only after Core forensic review:

```powershell
.\Target_Aware_Portability_P1_C\scripts\run_p1c_full_gate.ps1
```

Full = 7,200 replications.

## Resume behavior

Each scenario is checkpointed under the output `partial` directory.

If the process stops, rerun the same PowerShell command. Completed repetition IDs are retained and skipped.

## Main outputs

- `p1c_protocol.json`
- `p1c_scenarios.csv`
- `p1c_replication_results.csv`
- `p1c_scenario_summary.csv`
- `p1c_gate.csv`
- `partial\*.csv`
