# Criteo Frozen Execution Chain

The final Criteo workflow is a staged frozen pipeline. The stage names below
are provenance labels; they are not manuscript section names.

```text
raw CRITEO-UPLIFT v2.1
        |
        v
R0   X-only audit and shift-direction calibration
        |
        v
R0.1 full-X shift materialization
        |
        v
R1   population roles + fixed model library
        |
        v
R1.1 budget-fidelity/randomization audit
        |
        v
R1.2 propensity-adjusted source selection
        |
        v
R1F  exact policy materialization / finalization
        |
        v
R2   target-outcome-blind portability assessment
        |
        |  FREEZE
        v
R3   first target A,Y unlock + held-out benchmark
        |
        v
R4   evidence synthesis only
```

## Important gate interpretation

R1.1 is required as an input to R1.2, but its strict audit does **not** pass.
The supplied `criteo_r11_gate.csv` has `all_gate_pass = false` at the stage
summary level. R1.2 also retains a permanent prespecified diagnostic failure.
Neither failure is retrospectively relabeled as a PASS.

R1F corrects an implementation-level policy-materialization problem without
retraining candidate models or reversing the scientific R1.2 failure.

R2 is the first manuscript-facing portability assessment and uses no target
treatment/outcome information. R3 accesses target treatment and outcomes only
after the R2 outputs are frozen. R4 performs no new model or nuisance fitting.

## R11 dependency verification

The imported R11 source SHA-256 is:

`fa011f1d63e0394174e73e48989ad4b80882827c1c6c990b61fe4bbd29e3176e`

This exactly matches the `EXPECTED_R11_SHA256` hard-coded in the frozen R1.2
source, closing the previously missing R11 dependency.

## Raw data

The raw CRITEO-UPLIFT data are not redistributed in this repository. The
reproduction workflow must obtain the public dataset separately and verify the
frozen raw-data checksum documented in the repository.
