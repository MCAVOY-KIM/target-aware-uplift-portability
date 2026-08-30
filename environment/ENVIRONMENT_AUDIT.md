# Captured Project Environment Audit

## Capture

- Python: `Python 3.11.9`
- pip: `pip 26.2.1 from C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\.venv\Lib\site-packages\pip (python 3.11)`
- Platform:
  ```
  3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]
Windows-10-10.0.26200-SP0
  ```

The files in this directory were captured from the project's local
`SCIE 논문 프로젝트/.venv` on 2026-08-30.

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

- `pip_freeze.txt`: verbatim captured package snapshot.
- `requirements_lock_captured.txt`: same full snapshot, named for installation use.
- `requirements_frozen_source_direct.txt`: exact versions of packages directly
  imported by frozen manuscript source.
- `python_version.txt`: captured Python version.
- `pip_version.txt`: captured pip version.
- `system_info.txt`: Python build and Windows platform information.
- `verify_environment.py`: checks the principal package versions in an environment.

## Reproduction recommendation

For archival fidelity, retain the full captured lockfile. For a clean
reproduction environment, begin from Python 3.11 and install
`requirements_lock_captured.txt`, then run the verification script and the
stage-level frozen scripts.

A reproduction run in a future environment may require adjustments if archived
binary wheels are unavailable. Any such environment should be documented
separately rather than presented as the original captured environment.
