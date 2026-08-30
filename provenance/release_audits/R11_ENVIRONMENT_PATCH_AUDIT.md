# Frozen Source Import Audit — Complete Batch

This package was assembled directly from the user's frozen project folders.
No analysis source code was reconstructed from the manuscript.

## Imported frozen sources

- P1-B1 final/full simulation.
- P1-C rare-binary final/full simulation.
- Criteo R0, R0.1, R1, R1.1, R1.2, R1F, R2, R3, and R4_FIXED.
- Stage execution scripts, protocols, decision/freeze logs, and compact/final
  evidence outputs.
- User-provided project `requirements.txt`, preserved verbatim.
- SHA-256 manifests computed directly from the uploaded frozen files.

## R11 dependency closure

R11 is now included. Its source SHA-256 is:

`fa011f1d63e0394174e73e48989ad4b80882827c1c6c990b61fe4bbd29e3176e`

It exactly matches the hash required by the frozen R1.2 source.

## Environment limitation

The supplied requirements specify version ranges rather than an exact lockfile.
A direct-import audit also identified `joblib` and `matplotlib` as dependencies
of the frozen sources that are not explicitly listed in the supplied
requirements. See `environment/DEPENDENCY_AUDIT.md`.

Before public release, capture the existing original `.venv` if it is still the
environment used for the frozen analysis. Do not claim exact historical package
versions until this is verified.

## Intentional exclusions

- Raw CRITEO-UPLIFT data.
- `.venv`, caches, and `.pyc` files.
- Large serialized model/nuisance binaries.
- Smoke-run and duplicate partial outputs where complete final tables exist.
- Old archive ZIPs.

## Integrity status

The previously verified R4_FIXED hash chain for the primary R2/R3 artifacts
remains intact. The repository now contains the missing R11 source/output
dependency required to execute R1.2.
