# Public-Release Hygiene

Before public release, author-local filesystem paths are removed from public-facing
repository files.

The only frozen output whose bytes are intentionally changed for privacy is:

`outputs/criteo/r0/criteo_r0_summary.json`

Its `data_path` field originally recorded an author-local Windows path. The public
copy replaces only that field with:

`data/raw/criteo-research-uplift-v2.1.csv.gz`

The raw-data SHA-256, row count, feature list, PCA diagnostic values, seeds, outcome
roles, and blinding rule are unchanged. The original and public SHA-256 values are
recorded in `provenance/checksums/public_sanitization_manifest.csv`.

Primary R2/R3 frozen evidence files remain byte-identical and continue to be checked
with raw-byte SHA-256 hashes.
