# target-aware-uplift-portability

Reproducibility repository for the manuscript:

**Target-Aware Portability Assessment of Source-Selected Uplift Models under Population Shift**

**Author:** Dongyeon Kim  
**Affiliation:** Department of Big Data, Graduate School of Information and Communication Technology, Sungkyunkwan University, Seoul, Republic of Korea  
**ORCID:** 0009-0001-5151-2490

> **Pre-submission status:** keep this repository private until the reproducibility gate is closed and the manuscript GitHub URL is frozen.

## Scientific scope

The study asks whether an uplift model that has already been selected in a randomized source population remains practically competitive after deployment to a covariate-shifted target population when target outcomes are unavailable.

The inferential target is the **library-relative target regret of the source-selected model under target-adaptive treatment budgets**.

This repository does **not** claim:

- a new generic causal transport estimator;
- a new target-policy-learning algorithm;
- exact finite-sample confidence certification;
- natural external validation from CRITEO-UPLIFT; or
- exact preservation of target model rankings.

The repository retains negative and limiting evidence, including finite-sample undercoverage in difficult simulation regimes and the permanently failed prespecified R1.2 balance diagnostic.

## Two reproducibility tracks

### Track A — Frozen-evidence audit

This is the fastest audit and does **not** require the raw CRITEO-UPLIFT data.

It checks the imported frozen source/artifact hashes and rebuilds the final R4 evidence synthesis from the frozen outcome-blind R2 outputs and held-out R3 benchmark outputs.

```bash
python scripts/verify_frozen_repository.py
python scripts/verify_frozen_r4.py
python scripts/reproduce_manuscript_assets.py
```

### Track B — Full recomputation

This requires the public CRITEO-UPLIFT v2.1 raw data and can be computationally expensive.

1. Prepare the environment.
2. Download the raw dataset separately.
3. Verify its SHA-256.
4. Re-run the simulations and/or Criteo pipeline.

```bash
python environment/verify_environment.py
python scripts/verify_raw_data.py

python scripts/reproduce_simulations.py --which all

# The default Criteo recomputation stops at the outcome-blind R2 stage.
python scripts/reproduce_criteo_pipeline.py \
  --data data/raw/criteo-research-uplift-v2.1.csv.gz \
  --through r2
```

To attempt the held-out target benchmark:

```bash
python scripts/reproduce_criteo_pipeline.py \
  --data data/raw/criteo-research-uplift-v2.1.csv.gz \
  --through r3
```

The frozen R3 source intentionally verifies byte-level SHA-256 hashes of the R2 artifacts before unlocking target treatment/outcome information. A non-identical recomputation therefore stops rather than silently continuing. This is a provenance safeguard, not an error to bypass.

## Repository structure

```text
.
├── README.md
├── LICENSE
├── .gitignore
├── data/
│   └── README.md
├── environment/
│   ├── ENVIRONMENT_AUDIT.md
│   ├── environment_manifest.json
│   ├── python_version.txt
│   ├── pip_version.txt
│   ├── pip_freeze.txt
│   ├── requirements_lock_captured.txt
│   ├── requirements_frozen_source_direct.txt
│   ├── requirements_project_original.txt
│   ├── system_info.txt
│   └── verify_environment.py
├── src/
│   ├── simulation/
│   └── criteo/
├── scripts/
│   ├── reproduce_simulations.py
│   ├── reproduce_criteo_pipeline.py
│   ├── verify_raw_data.py
│   ├── verify_frozen_repository.py
│   ├── verify_frozen_r4.py
│   └── reproduce_manuscript_assets.py
├── outputs/
│   ├── simulation/
│   └── criteo/
├── provenance/
│   ├── checksums/
│   └── freeze_logs/
└── docs/
    ├── data_access.md
    ├── reproducibility.md
    ├── manuscript_mapping.md
    ├── criteo_execution_chain.md
    └── public_release_checklist.md
```

## Data

The raw CRITEO-UPLIFT data are **not redistributed**.

Expected local path:

```text
data/raw/criteo-research-uplift-v2.1.csv.gz
```

Frozen SHA-256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

See `docs/data_access.md`.

## Environment

The repository preserves the **captured project environment**:

- Python 3.11.9
- NumPy 2.4.6
- pandas 2.3.3
- SciPy 1.17.1
- scikit-learn 1.9.0
- joblib 1.5.3
- matplotlib 3.11.1

This is deliberately not labeled the exact historical environment for every frozen run because the available evidence does not independently prove that the virtual environment was never modified after every experiment. See `environment/ENVIRONMENT_AUDIT.md`.

## Frozen Criteo chain

```text
R0  X-only audit / shift calibration
 ↓
R0.1 full-X shift materialization
 ↓
R1  population roles + fixed model library
 ↓
R1.1 budget/randomization audit
 ↓
R1.2 propensity-adjusted selection
 ↓
R1F exact policy materialization
 ↓
R2  TARGET-OUTCOME-BLIND PORTABILITY ASSESSMENT
 ↓
     FROZEN
 ↓
R3  FIRST TARGET A,Y UNLOCK + HELD-OUT BENCHMARK
 ↓
R4  evidence synthesis only
```

R1.1/R1.2 diagnostic failures remain part of the permanent provenance. They are not retrospectively relabeled as passes.

## Frozen-output versus recomputation semantics

The `outputs/` directory contains frozen evidence artifacts used to support the submitted manuscript. Re-running a stochastic or platform-sensitive analysis may yield numerically equivalent but byte-different files.

The R2→R3→R4 chain intentionally contains SHA-256 locks. Do not edit or disable them to force a downstream run.

## License

Repository code is released under the MIT License at the repository root. The license does not grant redistribution rights for the CRITEO-UPLIFT dataset. Users must obtain the data separately from the source provider.
