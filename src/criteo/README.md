# Criteo source files

Copy only the **frozen stage scripts/configuration files actually used for the submitted manuscript**. Do not dump raw data or large intermediate model objects into Git.

## Local stage directories to review

- `Target_Aware_Portability_Criteo_R0`
- `Target_Aware_Portability_Criteo_R01`
- `Target_Aware_Portability_Criteo_R1`
- `Target_Aware_Portability_Criteo_R12`
- `Target_Aware_Portability_Criteo_R1F`
- `Target_Aware_Portability_Criteo_R2`
- `Target_Aware_Portability_Criteo_R3`
- `Target_Aware_Portability_Criteo_R4_FIXED`

## Confirmed run scripts

- R2: `scripts/run_criteo_r2.ps1`
- R3: `scripts/run_criteo_r3.ps1`

For each stage, copy the executable `.py`/`.ps1` scripts and small frozen configuration/decision-log files, then compute SHA-256 values. Large generated artifacts should be represented by hashes and compact manuscript-facing CSV summaries unless redistribution is genuinely required.

## Scientific chronology to preserve

R0/R0.1 X-only shift construction -> R1 source model library/selection -> R1.2 retained diagnostic FAIL -> R1F technical materialization correction -> R2 outcome-blind portability freeze -> R3 first target-outcome unlock -> R4 evidence synthesis.
