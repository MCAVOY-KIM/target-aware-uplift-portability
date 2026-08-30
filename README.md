# target-aware-uplift-portability

Reproducibility repository for the manuscript:

**Target-Aware Portability Assessment of Source-Selected Uplift Models under Population Shift**

Author: **Dongyeon Kim**  
Affiliation: Department of Big Data, Graduate School of Information and Communication Technology, Sungkyunkwan University, Seoul, Republic of Korea  
ORCID: **0009-0001-5151-2490**

> **Repository status:** private pre-submission reproducibility repository. The repository should be made public only after the reproducibility package has been frozen and checked against the submitted manuscript.

## What this repository is for

This repository is intended to reproduce and audit the paper's two evidence streams:

1. **Exact-truth simulation study** of target-aware portability assessment under population shift.
2. **Large-scale CRITEO-UPLIFT application** in which the target-outcome-blind portability assessment is frozen before target treatment/outcome information is unlocked for a held-out benchmark.

The repository is designed around a strict separation between:

- model training / source-side selection,
- target-policy adaptation,
- outcome-blind portability inference,
- held-out target-outcome benchmarking,
- frozen outputs and provenance.

## Scientific scope

The paper studies the target regret of an **already source-selected uplift model** relative to a fixed candidate library under target-adaptive treatment budgets. It does **not** claim a new generic transport estimator, a new target-policy-learning algorithm, exact finite-sample certification, or natural external validation from Criteo.

## Repository structure

```text
.
├── README.md
├── environment/
│   ├── README.md
│   └── requirements_TEMPLATE.txt
├── data/
│   └── README.md
├── src/
│   ├── simulation/
│   ├── criteo/
│   └── common/
├── configs/
│   ├── simulation/
│   └── criteo/
├── scripts/
│   ├── verify_checksums.py
│   ├── capture_environment.py
│   └── README.md
├── outputs/
│   ├── simulation/
│   ├── criteo/
│   ├── tables/
│   └── figures/
├── provenance/
│   ├── artifact_manifest.csv
│   ├── seeds.csv
│   ├── checksums/
│   └── freeze_logs/
└── docs/
    ├── data_access.md
    ├── reproducibility.md
    ├── manuscript_mapping.md
    └── scope_and_disclosure.md
```

## Data policy

The raw CRITEO-UPLIFT data are **not redistributed** in this repository. See [`docs/data_access.md`](docs/data_access.md) for the official source, expected local filename, row count, and SHA-256 verification procedure.

Expected raw file:

```text
data/raw/criteo-research-uplift-v2.1.csv.gz
```

Expected SHA-256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

## Reproducibility contract

Before the repository is made public, the following must be true:

- all scripts used for manuscript results are present;
- all configuration files are frozen;
- environment/package versions are recorded;
- raw data are excluded from Git;
- frozen manuscript tables/figures can be regenerated from documented inputs;
- provenance hashes match the submitted supplementary material;
- the target-outcome unlock chronology is documented;
- no result is recomputed post hoc merely to improve the reported conclusions.

## Quick verification

After placing locally available artifacts at the paths recorded in `provenance/artifact_manifest.csv`:

```bash
python scripts/verify_checksums.py
```

To capture the final submission environment:

```bash
python scripts/capture_environment.py
```

## Manuscript mapping

See [`docs/manuscript_mapping.md`](docs/manuscript_mapping.md) for the intended mapping between manuscript sections, tables/figures, and reproducibility artifacts.

## License

The repository code is intended to be released under the MIT License already configured at the repository root. This license does **not** grant redistribution rights for the CRITEO-UPLIFT dataset; users must obtain the dataset from its official source under the source provider's terms.
