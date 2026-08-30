# Public Release Checklist

Keep the repository **Private** until every required item below passes.

## Required before public release

- [ ] Repository root README reflects the submitted manuscript title.
- [ ] Author and ORCID are correct.
- [ ] Raw CRITEO-UPLIFT data are absent from Git history.
- [ ] `.venv`, caches, and serialized private/local artifacts are absent.
- [ ] `environment/` contains the captured project snapshot.
- [ ] `python scripts/verify_frozen_repository.py` passes.
- [ ] `python scripts/verify_frozen_r4.py` passes.
- [ ] Manuscript-facing figures/tables can be regenerated from documented frozen outputs.
- [ ] R1.1/R1.2 failed diagnostics remain visible.
- [ ] R2 target-outcome blinding is documented.
- [ ] R3 first target-outcome unlock is documented.
- [ ] No hard-coded local usernames, OneDrive paths, secrets, tokens, or private corporate paths remain in public-facing files.
- [ ] GitHub URL is inserted into the manuscript and Supplement only after the repository path is final.
- [ ] A release tag corresponding to the submitted manuscript is created (recommended: `v1.0-submission`).

## Recommended before public release

- [ ] Run a clean clone test in a new directory.
- [ ] Create a fresh Python 3.11 environment and run `environment/verify_environment.py`.
- [ ] Run the frozen-output audit without the raw dataset.
- [ ] Download the public CRITEO data separately and verify its checksum.
- [ ] Confirm that the top-level quick-start commands are copy/paste runnable.
- [ ] Review all repository files for accidental personal or proprietary information.

## Do not publish

- raw CRITEO data;
- corporate/project data;
- credentials or tokens;
- `.venv`;
- exploratory files not used by the manuscript unless clearly labeled as archival;
- altered outputs made after the scientific freeze to improve reported results.
