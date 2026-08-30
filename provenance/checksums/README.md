# Checksum semantics

This directory contains checksum manifests with different purposes.

## Source-code integrity

`source_sha256_canonical_lf.csv` is the authoritative cross-platform manifest for
the frozen manuscript source files.

Git can materialize text files with CRLF line endings on Windows and LF line
endings on Unix-like systems. Source verification therefore canonicalizes line
endings to LF before computing SHA-256. No other source-code characters are
normalized.

`source_sha256.csv` is retained as a historical import-time checksum record. It is
not the authoritative cross-platform source verifier.

## Frozen evidence integrity

Primary frozen evidence artifacts, especially the R2/R3 files used by the
outcome-blind freeze and target-outcome unlock chain, retain raw-byte SHA-256
verification. These hashes are not line-ending-normalized by the frozen repository
verifier.

## Public sanitization

`public_sanitization_manifest.csv` records the intentionally sanitized public copy
of the R0 summary, where only an author-local raw-data path was replaced by the
repository-relative `data/raw/` path. Scientific fields were not changed.

See `docs/cross_platform_integrity.md` and `docs/public_release_hygiene.md`.
