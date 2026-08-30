# Decision Log — R2 Forensic PASS → R3 Outcome Unlock

R2 is frozen before target outcome access.

Forensic findings:
- 45 pairwise contrast rows, 9 bound rows, 54 target-policy rows;
- no duplicate rows or non-finite inferential values;
- all nine point regrets and upper/lower bounds exactly recompute from the
  corresponding five competitor-minus-source contrasts;
- target-adapt top-q is exact in all 54 policies;
- maximum target-infer budget deviation = .000694;
- density-ratio ESS almost exactly recovers the design ESS:
  0.999987, 0.799098, 0.498712;
- estimated and oracle ratio upper regret bounds differ by less than ~1e-6
  across all nine cells;
- all R2 technical gates pass.

Frozen R2 interpretation before looking at target Y:
- all nine lower regret bounds are zero;
- minimum portability tolerance B_U ranges from .000150 to .000584;
- at epsilon=.0005, seven of nine cells are classified portable and
  null q=.3/.5 are uncertain;
- at epsilon >= .001, all nine cells are classified portable.

This is not yet judged correct or successful.

R3 now unlocks target A/Y solely to benchmark those frozen statements.

R1.2 strict propensity gate remains FAIL and Criteo remains secondary
large-scale application evidence.
