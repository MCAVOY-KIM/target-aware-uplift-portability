# Cross-Platform Integrity

## Source-code hashes

Git may materialize text files with different line endings on Windows and Unix-like systems.

The original frozen source files use LF line endings. A Windows checkout configured for CRLF can therefore have a different raw-byte SHA-256 even when the source text is identical.

For frozen `.py` sources, repository integrity is checked after canonicalizing line endings to LF. The expected canonical hashes are stored in:

`provenance/checksums/source_sha256_canonical_lf.csv`

This transformation changes **only line-ending representation**. It does not ignore any source-code characters.

## Evidence-artifact hashes

The primary frozen R2/R3 evidence files retain **raw-byte SHA-256 checks** because these artifacts are part of the outcome-blind freeze/provenance chain.

## Reproduced manuscript assets

Freshly regenerated figures/tables are written to:

`reproduction_runs/manuscript_assets/`

They do not overwrite the tracked frozen manuscript assets in `outputs/`.

PNG byte identity is not required across operating systems/rendering backends. The reproduction script regenerates the figures from the frozen numeric inputs and performs a semantic equality check for Table IV.
