# Target-Aware Uplift Portability

Reproducibility repository for the manuscript:

**Target-Aware Portability Assessment of Source-Selected Uplift Models under Population Shift**

**Author:** Dongyeon Kim  
**Affiliation:** Department of Big Data, Graduate School of Information and Communication Technology, Sungkyunkwan University, Seoul, Republic of Korea  
**ORCID:** https://orcid.org/0009-0001-5151-2490

The manuscript-submission repository snapshot is identified by the Git tag
`v1.0-submission`.

## Scientific scope

The study asks whether an uplift model that has already been selected in a randomized
source population remains practically competitive after deployment to a
covariate-shifted target population when target outcomes are unavailable.

The primary inferential object is the **library-relative target regret of the
source-selected model under target-adaptive treatment budgets**.

This repository does **not** claim:

- a new generic causal transport estimator;
- a new target-policy-learning algorithm;
- exact finite-sample confidence certification;
- natural external validation from CRITEO-UPLIFT; or
- exact preservation of target model rankings.

The repository intentionally retains negative and limiting evidence. In particular,
the prespecified R1.2 balance diagnostic remains a permanent scientific failure in
the provenance record, and difficult rare-binary simulation regimes show
finite-sample undercoverage. The R1F technical finalization does not retroactively
reverse the R1.2 failure.

## Reproducibility tracks

### Track A - Frozen-evidence audit

This is the fastest audit and does **not** require the raw CRITEO-UPLIFT data.

It verifies the frozen source/evidence chain, rebuilds the final R4 synthesis from
the frozen R2 and R3 artifacts, and regenerates manuscript-facing assets into
`reproduction_runs/`.

```bash
python scripts/verify_frozen_repository.py
python scripts/verify_frozen_r4.py
python scripts/reproduce_manuscript_assets.py
```

Expected high-level results include:

```text
Frozen source canonical-LF manifest (11 files): PASS
R2/R3 frozen evidence raw-byte hash chain: PASS
Frozen repository verification: PASS
Frozen R4 evidence synthesis: PASS
Table IV semantic equality with frozen table: PASS
```

### Track B - Full recomputation

This requires the public CRITEO-UPLIFT v2.1 raw data and can be computationally
expensive.

1. Prepare the Python environment.
2. Obtain the raw dataset separately.
3. Verify the raw-data SHA-256.
4. Re-run the simulations and/or Criteo pipeline.

```bash
python environment/verify_environment.py
python scripts/verify_raw_data.py

python scripts/reproduce_simulations.py --which all

# The default full Criteo recomputation stops at the outcome-blind R2 stage.
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

The frozen R3 source intentionally checks byte-level SHA-256 hashes of the R2
artifacts before target treatment/outcome information is unlocked. A recomputation
that is not byte-identical to the frozen R2 inputs therefore stops rather than
silently continuing. Do not disable this safeguard.

## Repository structure

```text
.
|-- README.md
|-- LICENSE
|-- CITATION.cff
|-- configs/
|-- data/
|   `-- README.md
|-- environment/
|   |-- ENVIRONMENT_AUDIT.md
|   |-- requirements_lock_captured.txt
|   |-- requirements_frozen_source_direct.txt
|   `-- verify_environment.py
|-- src/
|   |-- simulation/
|   `-- criteo/
|-- scripts/
|   |-- reproduce_simulations.py
|   |-- reproduce_criteo_pipeline.py
|   |-- verify_raw_data.py
|   |-- verify_frozen_repository.py
|   |-- verify_frozen_r4.py
|   |-- audit_public_privacy.py
|   `-- reproduce_manuscript_assets.py
|-- outputs/
|   |-- simulation/
|   `-- criteo/
|-- provenance/
|   |-- checksums/
|   |-- freeze_logs/
|   `-- release_audits/
`-- docs/
    |-- data_access.md
    |-- reproducibility.md
    |-- manuscript_mapping.md
    |-- criteo_execution_chain.md
    |-- cross_platform_integrity.md
    |-- public_release_hygiene.md
    `-- release_snapshot.md
```

## Data

The raw CRITEO-UPLIFT data are **not redistributed**.

Expected local path:

```text
data/raw/criteo-research-uplift-v2.1.csv.gz
```

Frozen raw-data SHA-256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

See `docs/data_access.md` for acquisition and verification details.

## Captured environment

The repository preserves the captured project environment used for the final
reproducibility audit:

- Python 3.11.9
- NumPy 2.4.6
- pandas 2.3.3
- SciPy 1.17.1
- scikit-learn 1.9.0
- joblib 1.5.3
- matplotlib 3.11.1

This is deliberately described as the **captured project environment**, not the
exact historical environment for every frozen run, because the available evidence
does not independently prove that the virtual environment was never modified after
every experiment.

See `environment/ENVIRONMENT_AUDIT.md`.

## Frozen Criteo application chain

```text
R0   X-only audit / shift calibration
 |
R0.1 full-X shift materialization
 |
R1   population roles + fixed model library
 |
R1.1 budget/randomization audit
 |
R1.2 propensity-adjusted selection
 |
R1F  exact policy materialization
 |
R2   TARGET-OUTCOME-BLIND PORTABILITY ASSESSMENT
 |
 |    FROZEN BEFORE TARGET OUTCOME UNLOCK
 |
R3   FIRST TARGET A,Y UNLOCK + HELD-OUT BENCHMARK
 |
R4   evidence synthesis only
```

The prespecified R1.2 balance failure remains visible in the permanent provenance
record.

## Frozen outputs and recomputation

The `outputs/` directory contains frozen evidence artifacts used by the manuscript.

Source-code integrity is checked using canonical-LF SHA-256 hashes so that Windows
and Unix line-ending materialization does not create false failures. Primary frozen
R2/R3 evidence artifacts retain raw-byte SHA-256 locks.

Freshly regenerated manuscript assets are written to:

```text
reproduction_runs/manuscript_assets/
```

Tracked frozen manuscript assets are not overwritten.

See:

- `docs/reproducibility.md`
- `docs/cross_platform_integrity.md`
- `docs/public_release_hygiene.md`
- `provenance/checksums/README.md`

## Citation

Citation metadata are provided in `CITATION.cff`.

Until the manuscript receives a permanent publication identifier, cite this
repository using the GitHub repository metadata. The citation file can be updated
after publication to include the final DOI without changing the frozen submission
tag.

## License

Repository code is released under the MIT License. The license does not grant
redistribution rights for the CRITEO-UPLIFT dataset; users must obtain the raw data
separately from the source provider.
