# Public Release Reproducibility Gate — Round 1

## Verified from frozen materials

**PASS**
- Frozen P1-B1 and P1-C source files are available.
- Frozen Criteo source chain R0 → R0.1 → R1 → R1.1 → R1.2 → R1F → R2 → R3 → R4 is available.
- R11 source SHA-256 matches the value required by R1.2.
- R4_FIXED's ten primary R2/R3 artifact hashes match the imported frozen files.
- The original frozen R4 code successfully rebuilds the evidence synthesis from the imported frozen R2/R3 outputs.
- Manuscript-facing figures/tables can be regenerated from compact frozen outputs.
- Captured project environment is documented.

## Important repository-layout patch

The original stage PowerShell scripts were written for the author's local
stage-folder layout. The public repository uses flattened `src/`, `outputs/`,
and `scripts/` directories.

Therefore the original PowerShell files are retained as provenance, while the
new cross-platform Python wrappers in this patch provide repository-native
reproduction commands.

## Pending before Public

**MUST CHECK**
- Append research-specific exclusions to `.gitignore`.
- Confirm no raw data, corporate files, credentials, or local private paths are tracked.
- Run `python scripts/verify_frozen_repository.py` in a fresh local clone.
- Run `python scripts/verify_frozen_r4.py` in a fresh local clone.
- Run `python scripts/reproduce_manuscript_assets.py`.
- Confirm the top-level README renders correctly on GitHub.
- Remove obsolete placeholders such as `environment/requirements_TEMPLATE.txt`.
- Create a submission tag only after the manuscript files and repository URL are frozen.

**PUBLIC RELEASE STATUS: NOT YET**
