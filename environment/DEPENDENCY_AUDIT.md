# Dependency Audit

## Status

The uploaded `requirements.txt` is preserved verbatim as
`requirements_project_original.txt`. It specifies compatible version ranges,
not the exact package versions that generated the frozen outputs.

## Direct imports in the frozen manuscript sources

Across the imported P1-B1, P1-C, and Criteo R0–R4 source files, the third-party
packages directly imported are:

- numpy
- pandas
- scipy
- scikit-learn
- joblib
- matplotlib

The uploaded project requirements declare:

- numpy
- pandas
- scipy
- scikit-learn
- lightgbm
- huggingface_hub

Therefore:

1. `joblib` and `matplotlib` are direct imports but are not explicitly listed
   in the uploaded project requirements. `joblib` is commonly installed as a
   scikit-learn dependency, but a reproducibility lockfile should still record
   its exact installed version.
2. `lightgbm` and `huggingface_hub` are present in the project requirements but
   are not directly imported by the currently frozen manuscript source set.
   They may belong to the broader project environment and are preserved rather
   than silently removed.

## Exact historical environment

The supplied requirements file alone does not identify the exact interpreter
and package versions used for every frozen run. Do not infer them from the
current machine or from `.pyc` files.

Before public release, capture the existing project `.venv` using
`scripts/environment/capture_original_environment.ps1`. If that `.venv` is the
environment used for the frozen runs, the resulting `pip_freeze.txt` and
`python_version.txt` should be committed under `environment/`.

If the original frozen-run environment cannot be established, state that fact
explicitly and provide a tested reproduction environment separately.
