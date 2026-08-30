# Criteo R4 Evidence Freeze

This stage performs no model fitting, no threshold selection, and no inference repair.
It only summarizes cryptographically frozen R2/R3 artifacts.

## Core empirical facts

- Point-estimated target-best model differs from the source-selected model in 9/9 scenario-budget cells.
- Yet held-out target benchmark point regret is below .0005 in all 9 cells.
- The maximum benchmark point regret is 0.000423816 (4.238 bp).
- The frozen R2 asymptotic upper bound exceeds the held-out benchmark point regret in all 9 cells.
- At epsilon=.0005, R2 makes 7 portable decisions and 2 uncertain decisions; benchmark point regret is <= epsilon in all 9, so there are no false-portable contradictions and two conservative abstentions.
- At epsilon >= .001, all 9 R2 decisions are portable and all 9 benchmark point regrets remain below tolerance.
- Benchmark simultaneous lower regret bound is >0 in only 3/9 cells. Thus point-estimated rank mismatch is much more common than statistically resolved practical inferiority.
- Across 45 directed contrasts, R2-vs-target correlation is 0.675, sign agreement is 0.756, and the R2 one-sided upper contrast bound lies above the target benchmark point in 44/45 contrasts.
- Target-only IPW sensitivity regret is below the corresponding R2 bound in all nine cells.

## Interpretation discipline

Do not write that R2 'proved' portability or achieved exact 95% coverage.
The R2 bounds are asymptotic and the earlier rare-binary simulations found finite-sample undercoverage under stronger shift.

Do not write that source/target rankings were preserved. They were not.

The defensible empirical message is:

> The identity of the point-estimated best uplift model was unstable across independently evaluated populations, but this did not imply materially large deployment regret. The target-outcome-blind portability assessment distinguished rank disagreement from practical decision loss and, in this application, produced conservative or tolerance-consistent decisions relative to a held-out target-outcome benchmark.

Criteo remains a secondary large-scale application because the predeclared R1.2 propensity-balance gate narrowly failed in the two shifted scenarios.
