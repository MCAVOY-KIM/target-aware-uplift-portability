# Simulation source files

This directory must contain the **frozen executable simulation source files**, copied from the local SCIE project without modification.

## Required source files

1. `p1c_rare_binary_simulation.py`
   - frozen SHA-256: `25523ca9b8118d36d00c26a7c4cb0ec08112817301e3a304b39293685fe2e965`
   - role: rare-binary finite-sample robustness gate used for the manuscript operating-boundary evidence.

2. `p1c1_inferential_diagnostic.py`
   - role: post-freeze diagnostic of the rare-binary undercoverage pockets.
   - do **not** use this diagnostic to alter the frozen P1-C method.

3. Frozen P1-B.1 simulation source used to produce the primary full-gate results.
   - copy the exact executed source from the local `Target_Aware_Portability_P1_B1` project.
   - record its SHA-256 in `provenance/checksums/frozen_artifacts.csv` before public release.

## Deliberately excluded

Early exploratory pilot files (for example, pre-freeze synthetic pilots) should not be presented as manuscript-generating source. They may be archived separately if desired, but the public reproducibility path should emphasize the frozen code that produced reported evidence.
