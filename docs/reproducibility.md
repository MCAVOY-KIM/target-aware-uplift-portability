# Reproducibility Guide

## 1. Environment

The repository contains both the original broad project requirements and a captured project-environment snapshot.

For archival inspection:

```bash
python environment/verify_environment.py
```

For a clean environment, Python 3.11 is recommended. The captured full snapshot is stored in:

```text
environment/requirements_lock_captured.txt
```

The smaller direct-import list is:

```text
environment/requirements_frozen_source_direct.txt
```

The captured environment is not claimed to be independently proven as the exact historical environment for every frozen run.

## 2. Frozen repository audit

No raw data are needed:

```bash
python scripts/verify_frozen_repository.py
python scripts/verify_frozen_r4.py
```

`verify_frozen_r4.py` executes the original frozen R4 source against the imported frozen R2/R3 outputs. It is an evidence-integrity audit, not a new experiment.

## 3. Manuscript assets

If the compact manuscript-output files from the repository are present:

```bash
python scripts/reproduce_manuscript_assets.py
```

This regenerates the manuscript-facing simulation and Criteo figures/tables from frozen compact outputs.

## 4. Simulations

```bash
python scripts/reproduce_simulations.py --which p1b1
python scripts/reproduce_simulations.py --which p1c
python scripts/reproduce_simulations.py --which all
```

Frozen settings:

- P1-B1: 1000 primary repetitions, 500 stress repetitions, 2000 bootstrap draws, epsilon 0.005, seed base 202608271.
- P1-C: 500 primary repetitions, 300 stress repetitions, 1500 bootstrap draws, epsilon 0.005, seed base 202608272.

Outputs are written under `reproduction_runs/simulation/`.

## 5. Criteo recomputation

Verify the raw file first.

```bash
python scripts/verify_raw_data.py
```

Then run through the target-outcome-blind R2 stage:

```bash
python scripts/reproduce_criteo_pipeline.py \
  --data data/raw/criteo-research-uplift-v2.1.csv.gz \
  --through r2
```

Outputs are written under `reproduction_runs/criteo/`.

### R3 outcome unlock

The original R3 source verifies exact R2 artifact SHA-256 values before target treatment/outcomes are used.

Therefore:

```bash
python scripts/reproduce_criteo_pipeline.py \
  --data data/raw/criteo-research-uplift-v2.1.csv.gz \
  --through r3
```

will proceed to R3 only if the recomputed R2 files satisfy the frozen hash lock. Do not disable this check.

## 6. Frozen evidence versus fresh recomputation

The repository preserves two different objects:

1. **Frozen evidence artifacts** used in the manuscript.
2. **Source code for recomputation**.

Byte-level identity is stronger than numerical reproducibility and can be sensitive to environment/platform details. The manuscript claims are based on the frozen evidence chain, whose hashes are auditable in this repository.
