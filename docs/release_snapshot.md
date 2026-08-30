# Manuscript Submission Repository Snapshot

## Tag

The manuscript-submission repository snapshot is identified by:

`v1.0-submission`

The tag is intended to remain immutable after creation.

## Scope of the freeze

The tag freezes the public reproducibility package supporting the manuscript
**Target-Aware Portability Assessment of Source-Selected Uplift Models under Population Shift**.

It includes:

- frozen simulation source and evidence artifacts;
- the frozen Criteo R0-R4 application chain;
- the outcome-blind R2 evidence and held-out R3 benchmark provenance;
- source/evidence checksum manifests;
- captured environment metadata;
- public reproduction wrappers;
- manuscript-facing compact figures/tables.

The raw CRITEO-UPLIFT data are not redistributed.

## Scientific integrity

The release preserves negative and limiting evidence. In particular:

- the prespecified R1.2 balance diagnostic remains a permanent failure;
- rare-binary simulations retain finite-sample undercoverage evidence;
- R1F is documented as a technical finalization and does not reverse the R1.2
  scientific failure;
- target outcomes remain locked until the R3 benchmark stage in the frozen
  provenance chain.

## Preflight commands

From a fresh clone with the captured environment installed:

```bash
python scripts/verify_frozen_repository.py
python scripts/verify_frozen_r4.py
python scripts/reproduce_manuscript_assets.py
python scripts/audit_public_privacy.py
```

The submission tag should be created only after all four commands pass and
`git status` reports a clean working tree.

## Post-publication update policy

The immutable submission tag should not be rewritten after manuscript submission.
If the paper is later accepted, publication metadata such as the DOI may be added
on the default branch and in a later release/tag while retaining
`v1.0-submission` unchanged.
