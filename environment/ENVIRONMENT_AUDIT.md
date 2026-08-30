# Captured Project Environment Audit

## Capture

- Python: `Python 3.11.9`
- pip: `pip 26.2.1 (Python 3.11)`
- Platform: `Windows-10-10.0.26200-SP0`

The package snapshot in this directory was captured from the project's local
virtual environment on 2026-08-30.

## Terminology

This repository calls this the **captured project environment**.

It is not labeled the *exact historical environment* because the available
evidence does not independently prove that the virtual environment was never
modified after every frozen experimental run.

## Frozen-source dependency consistency

Static import inspection of the 11 frozen manuscript source files identified
the following directly imported third-party packages:

| Package | Captured version |
|---|---:|
| numpy | 2.4.6 |
| pandas | 2.3.3 |
| scipy | 1.17.1 |
| scikit-learn | 1.9.0 |
| joblib | 1.5.3 |
| matplotlib | 3.11.1 |

All are present in the captured environment.

The broader project requirements also contained `lightgbm` and
`huggingface_hub`; the captured environment contains LightGBM 4.7.0 and
huggingface_hub 1.28.0. These packages are retained in the full lockfile,
although they are not directly imported by the currently frozen 11-source-file
manuscript pipeline.

## Files

- `pip_freeze.txt`: verbatim package-version snapshot.
- `requirements_lock_captured.txt`: full captured package-version snapshot.
- `requirements_frozen_source_direct.txt`: exact versions of packages directly
  imported by frozen manuscript source.
- `python_version.txt`: captured Python version.
- `pip_version.txt`: sanitized pip version record without an author-local path.
- `system_info.txt`: Python build and Windows platform information.
- `verify_environment.py`: checks the principal package versions.

## Reproduction recommendation

For archival fidelity, retain the full captured package-version snapshot. For a
clean reproduction environment, begin from Python 3.11, install
`requirements_lock_captured.txt`, then run the verification script and the
stage-level frozen scripts.

A reproduction run in a future environment may require adjustments if archived
binary wheels are unavailable. Any such environment should be documented
separately rather than presented as the original captured environment.
