# Utility scripts

- `verify_checksums.py`: verifies SHA-256 values for locally available files listed in `provenance/artifact_manifest.csv`.
- `capture_environment.py`: records Python/platform details and `pip freeze` output for the final submission environment.

Manuscript reproduction entry points should be added only after the final source files and configurations are frozen. Avoid placeholder scripts that appear to reproduce results but do not yet do so.
