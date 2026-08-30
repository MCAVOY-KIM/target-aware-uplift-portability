# Research Reframing Freeze — 2026-08-28

## Final working title

**Target-Aware Portability Assessment of Budget-Constrained Uplift Model Selection under Population Shift**

Alternative shorter title:
**When Does an Uplift Model Remain Portable? Target-Aware Assessment under Population Shift**

Do not use "finite-sample certified" or imply exact 95% finite-sample validity.

## Primary research question

Given:
- a fixed pretrained uplift-model library,
- randomized source outcomes,
- unlabeled covariates from a shifted target population,
- and target-adaptive treatment budgets,

**how can we quantify whether the uplift model selected in the source population remains practically competitive in the target population, without observing target outcomes at deployment time?**

## Estimand

For model m and target treatment budget q,

G_T(m,q) = E_T[ pi^T_{m,q}(X) tau(X) ].

The deployment policy is target-adaptive:

pi^T_{m,q}(X) = 1{s_m(X) >= c^T_{m,q}},

where c^T_{m,q} is estimated using target covariates only.

For source-selected model m_S(q), target regret is

R_T^S(q) = max_j { G_T(j,q) - G_T(m_S(q),q) }.

## Primary inferential output

Transported doubly robust estimates of competitor-minus-source policy gain contrasts.

Use asymptotic simultaneous one-sided bounds across the 15 directed contrasts.

Define:

Upper portability regret bound:
B_U(q) = max(0, max_j U_{j,m_S,q})

Lower non-portability evidence bound:
B_L(q) = max(0, max_j L_{j,m_S,q})

For a predeclared practical tolerance epsilon:

- PORTABLE if B_U(q) <= epsilon
- EVIDENCE OF NON-PORTABILITY if B_L(q) > epsilon
- UNCERTAIN otherwise

These are uncertainty-aware asymptotic assessments, not finite-sample exact guarantees.

## Contribution claims that are allowed

C1. Formulate source-selected uplift-model portability under population shift as target regret assessment for target-adaptive budget-constrained policies.

C2. Combine source randomized outcomes and unlabeled target covariates to estimate target policy-gain differences for a fixed pretrained uplift-model library using a transported doubly robust estimator.

C3. Provide source-specific simultaneous **asymptotic** regret bounds that support a portable / uncertain / evidence-of-non-portability decision rather than forced model reuse.

C4. Empirically characterize how overlap, outcome rarity, sample size, policy separation, and treatment budget affect safety and informativeness.

C5. Demonstrate the workflow on the large randomized Criteo uplift benchmark using target outcomes only as a held-out benchmark, not as an input to the portability assessment.

## Claims that are prohibited

Do NOT claim novelty for:
- doubly robust transportability itself;
- importance weighting;
- confidence intervals in general;
- abstention in general;
- set-valued policy learning in general;
- budget-constrained uplift in general;
- stability-aware uplift in general.

Do NOT claim:
- exact finite-sample 95% certification;
- universal superiority of the method;
- natural external validation from Criteo (the target population shift is emulated from real covariates);
- target-outcome-free proof of real-world portability.

## Required limitation statement

The Gaussian simultaneous bounds are asymptotic. Rare binary simulations showed moderate finite-sample undercoverage under stronger population shift and well-separated candidate policies. Bootstrap variants tested during method development did not provide a reliable universal correction. This limitation must remain visible in the manuscript.

## Novelty positioning

The defensible gap is the **joint problem**:
fixed uplift-model library + source randomized outcomes + unlabeled shifted target X + target-adaptive top-q policies + source-model target-regret assessment.

The paper is not positioned as a new generic transportability estimator or a new generic uncertainty/abstention framework.
