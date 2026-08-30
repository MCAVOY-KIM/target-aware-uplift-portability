from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy.stats import norm

ALPHA = 0.05
P = 10
M = 6
BUDGETS_DEFAULT = (0.10, 0.30, 0.50)
EPSILON_DEFAULT = 0.005

# Treatment-effect surface tau(x) = b'x + x'Hx.
BETA_TAU = np.zeros(P)
BETA_TAU[0] = 0.15
BETA_TAU[1] = 0.10
BETA_TAU[2] = 0.05
H_TAU = np.zeros((P, P))
H_TAU[0, 1] = H_TAU[1, 0] = 0.10  # contributes 0.20*x1*x2
H_TAU[2, 2] = -0.03

# Baseline outcome surface.
BETA_MU0 = np.zeros(P)
BETA_MU0[3] = 0.15
BETA_MU0[4] = -0.10
MU0_INTERCEPT = 0.20
NOISE_SD = 1.0
PROPENSITY = 0.5

# Diverse but deterministic pretrained score prototypes.
_PROTOS = np.zeros((M, P))
_PROTOS[0, 0] = 1.0
_PROTOS[1, 1] = 1.0
_PROTOS[2, 0] = 1.0; _PROTOS[2, 1] = 1.0
_PROTOS[3, 2] = 1.0
_PROTOS[4, 0] = 1.0; _PROTOS[4, 1] = -1.0
_PROTOS[5, 0] = -1.0
_BASE = _PROTOS[2] / np.linalg.norm(_PROTOS[2])
SEP_BLEND = {"near": 0.08, "moderate": 0.40, "clear": 0.95}
TAU_SCALE = {"near": 0.50, "moderate": 1.00, "clear": 3.00}

PAIR_INDEX = [(j, m) for j in range(M) for m in range(j + 1, M)]


@dataclass(frozen=True)
class Scenario:
    name: str
    n_source: int
    n_target: int
    ess_target: float
    separation: str
    shift_relevance: str
    nuisance: str
    reps: int


def normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n < 1e-12:
        return v.copy()
    return v / n


def candidate_library(separation: str) -> np.ndarray:
    s = SEP_BLEND[separation]
    rows = []
    for proto in _PROTOS:
        v = normalize(proto)
        w = (1.0 - s) * _BASE + s * v
        if np.linalg.norm(w) < 1e-10:
            w = v
        rows.append(normalize(w))
    return np.asarray(rows)


def target_delta(ess_target: float, relevance: str) -> np.ndarray:
    # For X_S~N(0,I), X_T~N(delta,I), asymptotic ESS/n = exp(-||delta||^2).
    magnitude = math.sqrt(max(0.0, -math.log(float(ess_target))))
    delta = np.zeros(P)
    if relevance == "relevant":
        delta[0] = magnitude
    elif relevance == "irrelevant":
        delta[7] = magnitude
    else:
        raise ValueError(relevance)
    return delta


def tau_true(x: np.ndarray, scale: float = 1.0) -> np.ndarray:
    linear = x @ BETA_TAU
    quad = np.einsum("ni,ij,nj->n", x, H_TAU, x)
    return scale * (linear + quad)


def mu0_true(x: np.ndarray) -> np.ndarray:
    return MU0_INTERCEPT + x @ BETA_MU0


def make_data(n: int, delta: np.ndarray, rng: np.random.Generator, with_outcome: bool, tau_scale: float = 1.0) -> Dict[str, np.ndarray]:
    x = rng.normal(size=(n, P)) + delta
    out = {"x": x}
    if with_outcome:
        a = rng.binomial(1, PROPENSITY, size=n).astype(float)
        y = mu0_true(x) + a * tau_true(x, tau_scale) + rng.normal(scale=NOISE_SD, size=n)
        out.update({"a": a, "y": y})
    return out


def basis(x: np.ndarray, correct: bool) -> np.ndarray:
    cols = [np.ones(len(x)), x]
    if correct:
        cols.extend([(x[:, 0] * x[:, 1])[:, None], (x[:, 2] ** 2)[:, None]])
    return np.column_stack(cols)


def fit_outcome_nuisance(train: Dict[str, np.ndarray], misspecified: bool) -> Tuple[np.ndarray, np.ndarray, bool]:
    x, a, y = train["x"], train["a"], train["y"]
    correct = not misspecified
    z = basis(x, correct=correct)
    coefs = []
    for arm in (0.0, 1.0):
        mask = a == arm
        coef, *_ = np.linalg.lstsq(z[mask], y[mask], rcond=None)
        coefs.append(coef)
    return coefs[0], coefs[1], correct


def predict_mu(x: np.ndarray, nuisance: Tuple[np.ndarray, np.ndarray, bool]) -> Tuple[np.ndarray, np.ndarray]:
    c0, c1, correct = nuisance
    z = basis(x, correct=correct)
    return z @ c0, z @ c1


def fit_ratio_delta(source_train_x: np.ndarray, target_adapt_x: np.ndarray, misspecified: bool) -> np.ndarray:
    d = target_adapt_x.mean(axis=0) - source_train_x.mean(axis=0)
    if misspecified:
        # Deliberately wrong but smooth model in every shift direction.
        d = 0.50 * d
    return d


def ratio_normal_shift(x: np.ndarray, delta_hat: np.ndarray) -> np.ndarray:
    logw = x @ delta_hat - 0.5 * float(delta_hat @ delta_hat)
    # Avoid numerical overflow in stress cells while not materially affecting supported ESS regimes.
    logw = np.clip(logw, -30.0, 30.0)
    return np.exp(logw)


def score_matrix(x: np.ndarray, W: np.ndarray) -> np.ndarray:
    return x @ W.T


def thresholds_from_sample(scores: np.ndarray, budgets: Tuple[float, ...]) -> np.ndarray:
    th = np.empty((len(budgets), M))
    for qi, q in enumerate(budgets):
        th[qi] = np.quantile(scores, 1.0 - q, axis=0)
    return th


def policy_tensor(scores: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
    # Returns n x Q x M boolean tensor.
    return scores[:, None, :] >= thresholds[None, :, :]


def exact_gain_linear_quadratic_policy(w: np.ndarray, threshold: float, delta: np.ndarray, tau_scale: float = 1.0) -> float:
    """E[(b'X + X'HX) 1{w'X >= threshold}] for X~N(delta,I), normalized w."""
    u = normalize(w)
    # w is normalized in our library, but retain generic scaling.
    scale = np.linalg.norm(w)
    if scale < 1e-12:
        return 0.0
    c = threshold / scale
    mu = float(u @ delta)
    z = c - mu
    q = float(norm.sf(z))
    ph = float(norm.pdf(z))
    first = delta * q + u * ph
    second = (
        (np.outer(delta, delta) + np.eye(P)) * q
        + (np.outer(delta, u) + np.outer(u, delta)) * ph
        + np.outer(u, u) * z * ph
    )
    return float(tau_scale * (BETA_TAU @ first + np.sum(H_TAU * second)))


def exact_gains(W: np.ndarray, thresholds: np.ndarray, delta: np.ndarray, tau_scale: float = 1.0) -> np.ndarray:
    Q = thresholds.shape[0]
    g = np.empty((Q, M))
    for qi in range(Q):
        for m in range(M):
            g[qi, m] = exact_gain_linear_quadratic_policy(W[m], thresholds[qi, m], delta, tau_scale)
    return g


def source_select_winners(
    source_train: Dict[str, np.ndarray],
    source_select: Dict[str, np.ndarray],
    W: np.ndarray,
    budgets: Tuple[float, ...],
    outcome_nuisance,
) -> np.ndarray:
    th = thresholds_from_sample(score_matrix(source_train["x"], W), budgets)
    pi = policy_tensor(score_matrix(source_select["x"], W), th).astype(float)
    mu0, mu1 = predict_mu(source_select["x"], outcome_nuisance)
    resid = (
        source_select["a"] / PROPENSITY * (source_select["y"] - mu1)
        - (1.0 - source_select["a"]) / (1.0 - PROPENSITY) * (source_select["y"] - mu0)
    )
    mudiff = mu1 - mu0
    est = (pi * mudiff[:, None, None]).mean(axis=0) + (pi * resid[:, None, None]).mean(axis=0)
    return est.argmax(axis=1)


def nearest_psd_corr(corr: np.ndarray) -> np.ndarray:
    corr = (corr + corr.T) / 2.0
    vals, vecs = np.linalg.eigh(corr)
    vals = np.clip(vals, 1e-10, None)
    x = (vecs * vals) @ vecs.T
    d = np.sqrt(np.clip(np.diag(x), 1e-12, None))
    x = x / np.outer(d, d)
    np.fill_diagonal(x, 1.0)
    return (x + x.T) / 2.0


def gaussian_max_t_critical(cov: np.ndarray, alpha: float, draws: int, rng: np.random.Generator) -> float:
    se = np.sqrt(np.clip(np.diag(cov), 1e-16, None))
    corr = cov / np.outer(se, se)
    corr = nearest_psd_corr(corr)
    vals, vecs = np.linalg.eigh(corr)
    L = vecs @ np.diag(np.sqrt(np.clip(vals, 0.0, None)))
    z = rng.normal(size=(draws, len(se))) @ L.T
    return float(np.quantile(np.max(np.abs(z), axis=1), 1.0 - alpha))



def gaussian_one_sided_max_t_critical(cov: np.ndarray, alpha: float, draws: int, rng: np.random.Generator) -> float:
    """Critical value for max_k Z_k, used only for preselected-source portability upper bounds."""
    se = np.sqrt(np.clip(np.diag(cov), 1e-16, None))
    corr = cov / np.outer(se, se)
    corr = nearest_psd_corr(corr)
    vals, vecs = np.linalg.eigh(corr)
    L = vecs @ np.diag(np.sqrt(np.clip(vals, 0.0, None)))
    z = rng.normal(size=(draws, len(se))) @ L.T
    return float(np.quantile(np.max(z, axis=1), 1.0 - alpha))


def build_ordered_bounds(pair_l: np.ndarray, pair_u: np.ndarray, Q: int) -> Tuple[np.ndarray, np.ndarray]:
    L = np.zeros((Q, M, M))
    U = np.zeros((Q, M, M))
    k = 0
    for qi in range(Q):
        for j, m in PAIR_INDEX:
            # Stored contrast is G_j - G_m.
            L[qi, j, m] = pair_l[k]
            U[qi, j, m] = pair_u[k]
            L[qi, m, j] = -pair_u[k]
            U[qi, m, j] = -pair_l[k]
            k += 1
    return L, U


def one_rep(
    seed: int,
    scenario: Scenario,
    budgets: Tuple[float, ...],
    epsilon: float,
    bootstrap_draws: int,
) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    W = candidate_library(scenario.separation)
    delta = target_delta(scenario.ess_target, scenario.shift_relevance)

    ns_tr = int(round(scenario.n_source * 0.30))
    ns_sel = int(round(scenario.n_source * 0.20))
    ns_inf = scenario.n_source - ns_tr - ns_sel
    nt_ad = int(round(scenario.n_target * 0.25))
    nt_inf = scenario.n_target - nt_ad

    tau_scale = TAU_SCALE[scenario.separation]
    source_train = make_data(ns_tr, np.zeros(P), rng, True, tau_scale)
    source_select = make_data(ns_sel, np.zeros(P), rng, True, tau_scale)
    source_infer = make_data(ns_inf, np.zeros(P), rng, True, tau_scale)
    target_adapt = make_data(nt_ad, delta, rng, False, tau_scale)
    target_infer = make_data(nt_inf, delta, rng, False, tau_scale)

    out_miss = scenario.nuisance in ("outcome_misspecified", "both_misspecified")
    ratio_miss = scenario.nuisance in ("ratio_misspecified", "both_misspecified")
    out_nuis = fit_outcome_nuisance(source_train, misspecified=out_miss)
    d_hat = fit_ratio_delta(source_train["x"], target_adapt["x"], misspecified=ratio_miss)

    source_winner = source_select_winners(source_train, source_select, W, budgets, out_nuis)

    target_th = thresholds_from_sample(score_matrix(target_adapt["x"], W), budgets)
    pi_t = policy_tensor(score_matrix(target_infer["x"], W), target_th).astype(float)
    pi_s = policy_tensor(score_matrix(source_infer["x"], W), target_th).astype(float)

    mu0_t, mu1_t = predict_mu(target_infer["x"], out_nuis)
    mu0_s, mu1_s = predict_mu(source_infer["x"], out_nuis)
    mudiff_t = mu1_t - mu0_t
    resid_s = (
        source_infer["a"] / PROPENSITY * (source_infer["y"] - mu1_s)
        - (1.0 - source_infer["a"]) / (1.0 - PROPENSITY) * (source_infer["y"] - mu0_s)
    )
    r_s = ratio_normal_shift(source_infer["x"], d_hat)

    # Q x M estimated gains.
    plugin = (pi_t * mudiff_t[:, None, None]).mean(axis=0)
    aug = (pi_s * (r_s * resid_s)[:, None, None]).mean(axis=0)
    ghat = plugin + aug

    # Per-observation contributions for covariance estimation.
    # Shapes: n x Q x M, then flatten Q*M.
    phi_t_models = pi_t * mudiff_t[:, None, None]
    phi_s_models = pi_s * (r_s * resid_s)[:, None, None]
    phi_t_models -= phi_t_models.mean(axis=0, keepdims=True)
    phi_s_models -= phi_s_models.mean(axis=0, keepdims=True)

    true_g = exact_gains(W, target_th, delta, tau_scale)
    Q = len(budgets)

    est_pairs = []
    true_pairs = []
    pair_t_cols = []
    pair_s_cols = []
    for qi in range(Q):
        for j, m in PAIR_INDEX:
            est_pairs.append(ghat[qi, j] - ghat[qi, m])
            true_pairs.append(true_g[qi, j] - true_g[qi, m])
            pair_t_cols.append(phi_t_models[:, qi, j] - phi_t_models[:, qi, m])
            pair_s_cols.append(phi_s_models[:, qi, j] - phi_s_models[:, qi, m])
    est_pairs = np.asarray(est_pairs)
    true_pairs = np.asarray(true_pairs)
    XT = np.column_stack(pair_t_cols)
    XS = np.column_stack(pair_s_cols)
    cov = (XT.T @ XT) / (nt_inf * max(nt_inf - 1, 1)) + (XS.T @ XS) / (ns_inf * max(ns_inf - 1, 1))
    se = np.sqrt(np.clip(np.diag(cov), 1e-16, None))
    crit = gaussian_max_t_critical(cov, ALPHA, bootstrap_draws, rng)
    lower = est_pairs - crit * se
    upper = est_pairs + crit * se

    simultaneous_coverage = float(np.all((true_pairs >= lower) & (true_pairs <= upper)))
    L, U = build_ordered_bounds(lower, upper, Q)

    # P1-B.1 primary decision family:
    # source winner is selected on an independent source_select split, so for deployment
    # certification we need only the directed contrasts G_j - G_ms(q), j != ms(q),
    # jointly across all budgets. This is at most (M-1)*Q comparisons, not all 45
    # unordered model-pair contrasts. The family is directional, so use max Z rather
    # than max |Z| to construct simultaneous upper bounds.
    src_est = []
    src_true = []
    src_t_cols = []
    src_s_cols = []
    src_meta = []
    for qi in range(Q):
        ms = int(source_winner[qi])
        for j in range(M):
            if j == ms:
                continue
            src_est.append(ghat[qi, j] - ghat[qi, ms])
            src_true.append(true_g[qi, j] - true_g[qi, ms])
            src_t_cols.append(phi_t_models[:, qi, j] - phi_t_models[:, qi, ms])
            src_s_cols.append(phi_s_models[:, qi, j] - phi_s_models[:, qi, ms])
            src_meta.append((qi, j, ms))

    src_est = np.asarray(src_est)
    src_true = np.asarray(src_true)
    XTs = np.column_stack(src_t_cols)
    XSs = np.column_stack(src_s_cols)
    cov_src = (XTs.T @ XTs) / (nt_inf * max(nt_inf - 1, 1)) + (XSs.T @ XSs) / (ns_inf * max(ns_inf - 1, 1))
    se_src = np.sqrt(np.clip(np.diag(cov_src), 1e-16, None))
    crit_src = gaussian_one_sided_max_t_critical(cov_src, ALPHA, bootstrap_draws, rng)
    upper_src = src_est + crit_src * se_src
    source_directed_simultaneous_coverage = float(np.all(src_true <= upper_src))

    # Map source-specific upper bounds back to budget for regret certification.
    source_specific_bounds = np.zeros(Q, dtype=float)
    for qi in range(Q):
        vals = [upper_src[k] for k, meta in enumerate(src_meta) if meta[0] == qi]
        source_specific_bounds[qi] = float(max(0.0, np.max(vals)))

    set_sizes = []
    set_best_covered = []
    source_bound_covered = []
    source_certified = []
    source_false_cert = []
    source_specific_bound_covered = []
    source_specific_certified = []
    source_specific_false_cert = []
    forced_unsafe = []
    forced_regret = []
    source_true_regret = []
    portability_bounds = []

    for qi in range(Q):
        # Model m remains if nobody j is significantly better: L[j,m] <= 0 for all j.
        cset = [m for m in range(M) if np.all(L[qi, :, m] <= 0.0 + 1e-15)]
        set_sizes.append(len(cset))
        best = int(np.argmax(true_g[qi]))
        set_best_covered.append(float(best in cset))

        ms = int(source_winner[qi])
        true_regret_s = float(np.max(true_g[qi]) - true_g[qi, ms])
        bound_s = float(max(0.0, np.max(U[qi, :, ms])))
        bound_src_specific = float(source_specific_bounds[qi])
        source_true_regret.append(true_regret_s)
        portability_bounds.append(bound_s)

        # Legacy/global all-pairs bound retained for audit.
        source_bound_covered.append(float(true_regret_s <= bound_s + 1e-12))
        cert = bound_s <= epsilon
        source_certified.append(float(cert))
        source_false_cert.append(float(cert and true_regret_s > epsilon))

        # P1-B.1 primary source-specific portability certificate.
        source_specific_bound_covered.append(float(true_regret_s <= bound_src_specific + 1e-12))
        cert_ss = bound_src_specific <= epsilon
        source_specific_certified.append(float(cert_ss))
        source_specific_false_cert.append(float(cert_ss and true_regret_s > epsilon))

        mf = int(np.argmax(ghat[qi]))
        regf = float(np.max(true_g[qi]) - true_g[qi, mf])
        forced_regret.append(regf)
        forced_unsafe.append(float(regf > epsilon))

    true_ess = math.exp(-float(delta @ delta))
    # Estimated ESS on source inference based on fitted ratio.
    est_ess = float((r_s.sum() ** 2) / (len(r_s) * np.sum(r_s ** 2)))

    return {
        "simultaneous_pairwise_coverage": simultaneous_coverage,
        "optimal_set_all_budgets_coverage": float(all(x == 1.0 for x in set_best_covered)),
        "portability_bound_all_budgets_coverage": float(all(x == 1.0 for x in source_bound_covered)),
        "source_specific_contrast_upper_coverage": source_directed_simultaneous_coverage,
        "source_specific_bound_all_budgets_coverage": float(all(x == 1.0 for x in source_specific_bound_covered)),
        "source_specific_certificate_rate": float(np.mean(source_specific_certified)),
        "source_specific_false_certificate_rate_unconditional": float(np.mean(source_specific_false_cert)),
        "num_source_specific_certified": int(np.sum(source_specific_certified)),
        "num_source_specific_false_certified": int(np.sum(source_specific_false_cert)),
        "mean_source_specific_portability_bound": float(np.mean(source_specific_bounds)),
        "source_specific_critical_value": float(crit_src),
        "mean_confidence_set_size": float(np.mean(set_sizes)),
        "singleton_rate": float(np.mean(np.asarray(set_sizes) == 1)),
        "source_certificate_rate": float(np.mean(source_certified)),
        "source_false_certificate_rate_unconditional": float(np.mean(source_false_cert)),
        "num_source_certified": int(np.sum(source_certified)),
        "num_source_false_certified": int(np.sum(source_false_cert)),
        "forced_unsafe_rate": float(np.mean(forced_unsafe)),
        "num_forced_unsafe": int(np.sum(forced_unsafe)),
        "mean_forced_regret": float(np.mean(forced_regret)),
        "mean_source_true_regret": float(np.mean(source_true_regret)),
        "mean_portability_bound": float(np.mean(portability_bounds)),
        "true_ess_ratio": float(true_ess),
        "estimated_ess_ratio": est_ess,
        "critical_value": crit,
    }


def core_scenarios(reps: int) -> List[Scenario]:
    out = []
    for n in (5000, 20000):
        for ess in (0.8, 0.5, 0.3):
            for sep in ("near", "clear"):
                out.append(Scenario(
                    name=f"core_n{n}_ess{ess}_{sep}",
                    n_source=n, n_target=n, ess_target=ess,
                    separation=sep, shift_relevance="relevant",
                    nuisance="both_correct", reps=reps,
                ))
    return out


def stress_scenarios(reps: int) -> List[Scenario]:
    out = [
        Scenario("stress_irrelevant", 20000, 20000, 0.5, "moderate", "irrelevant", "both_correct", reps),
        Scenario("stress_outcome_misspec", 20000, 20000, 0.5, "moderate", "relevant", "outcome_misspecified", reps),
        Scenario("stress_ratio_misspec", 20000, 20000, 0.5, "moderate", "relevant", "ratio_misspecified", reps),
        Scenario("stress_both_misspec", 20000, 20000, 0.5, "moderate", "relevant", "both_misspecified", reps),
    ]
    return out


def scenario_from_args(args) -> List[Scenario]:
    if args.mode == "smoke":
        return [
            Scenario("smoke_near", 2000, 2000, 0.5, "near", "relevant", "both_correct", args.reps),
            Scenario("smoke_clear", 2000, 2000, 0.5, "clear", "relevant", "both_correct", args.reps),
            Scenario("smoke_dr_outcome_misspec", 2000, 2000, 0.5, "moderate", "relevant", "outcome_misspecified", args.reps),
        ]
    if args.mode == "calibration":
        return core_scenarios(args.reps)
    if args.mode == "full":
        return core_scenarios(args.reps) + stress_scenarios(args.stress_reps)
    raise ValueError(args.mode)


def summarize(raw: pd.DataFrame, scenario_df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "simultaneous_pairwise_coverage",
        "optimal_set_all_budgets_coverage",
        "portability_bound_all_budgets_coverage",
        "source_specific_contrast_upper_coverage",
        "source_specific_bound_all_budgets_coverage",
        "source_specific_certificate_rate",
        "source_specific_false_certificate_rate_unconditional",
        "num_source_specific_certified",
        "num_source_specific_false_certified",
        "mean_source_specific_portability_bound",
        "source_specific_critical_value",
        "mean_confidence_set_size",
        "singleton_rate",
        "source_certificate_rate",
        "source_false_certificate_rate_unconditional",
        "num_source_certified",
        "num_source_false_certified",
        "forced_unsafe_rate",
        "num_forced_unsafe",
        "mean_forced_regret",
        "mean_source_true_regret",
        "mean_portability_bound",
        "true_ess_ratio",
        "estimated_ess_ratio",
        "critical_value",
    ]
    rows = []
    for name, g in raw.groupby("scenario", sort=False):
        meta = scenario_df.loc[scenario_df["name"] == name].iloc[0].to_dict()
        row = {"scenario": name}
        row.update({k: meta[k] for k in ["n_source", "n_target", "ess_target", "separation", "shift_relevance", "nuisance", "reps"]})
        for m in metrics:
            row[m] = float(g[m].mean())
            row[m + "_mcse"] = float(g[m].std(ddof=1) / math.sqrt(len(g))) if len(g) > 1 else np.nan
        total_cert = float(g["num_source_certified"].sum())
        total_false = float(g["num_source_false_certified"].sum())
        row["source_false_certificate_rate_conditional"] = (total_false / total_cert) if total_cert > 0 else np.nan
        total_cert_ss = float(g["num_source_specific_certified"].sum())
        total_false_ss = float(g["num_source_specific_false_certified"].sum())
        row["source_specific_false_certificate_rate_conditional"] = (total_false_ss / total_cert_ss) if total_cert_ss > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def make_gate(summary: pd.DataFrame, mode: str) -> pd.DataFrame:
    rows = []
    if mode == "calibration":
        cov_lo, cov_hi, bound_lo = 0.90, 0.99, 0.90
    else:
        cov_lo, cov_hi, bound_lo = 0.93, 0.97, 0.93

    for _, r in summary.iterrows():
        is_core = r["scenario"].startswith("core_")
        if mode == "smoke":
            pairwise_pass = src_upper_pass = bound_pass = false_cert_pass = informative_pass = np.nan
        else:
            # Global two-sided all-pairs CI is retained as a secondary validity diagnostic.
            pairwise_pass = bool(cov_lo <= r["simultaneous_pairwise_coverage"] <= cov_hi)

            # Primary P1-B.1 validity: simultaneous one-sided upper coverage for only
            # the preselected source winner vs its competitors, across all budgets.
            src_upper_pass = bool(cov_lo <= r["source_specific_contrast_upper_coverage"] <= cov_hi)
            bound_pass = bool(r["source_specific_bound_all_budgets_coverage"] >= bound_lo)

            cond_false = r["source_specific_false_certificate_rate_conditional"]
            false_cert_pass = bool(np.isnan(cond_false) or cond_false <= 0.05)

            informative_pass = np.nan
            if is_core and r["separation"] == "clear" and int(r["n_source"]) == 20000 and float(r["ess_target"]) >= 0.5:
                # Same 70% threshold as the original Core Gate, but now applied to the
                # primary deployment object: ability to certify the independently
                # source-selected model as epsilon-portable.
                informative_pass = bool(r["source_specific_certificate_rate"] >= 0.70)

        rows.append({
            "scenario": r["scenario"],
            "global_pairwise_coverage_pass": pairwise_pass,
            "source_specific_upper_coverage_pass": src_upper_pass,
            "source_specific_bound_pass": bound_pass,
            "source_specific_false_certificate_conditional_pass_le_05": false_cert_pass,
            "clear_source_certificate_informativeness_pass_ge_70": informative_pass,
        })

    gate = pd.DataFrame(rows)
    if mode != "smoke":
        core = gate[gate["scenario"].str.startswith("core_")]
        gate.attrs["core_global_pairwise_coverage_pass"] = bool(core["global_pairwise_coverage_pass"].fillna(False).all())
        gate.attrs["core_source_specific_upper_coverage_pass"] = bool(core["source_specific_upper_coverage_pass"].fillna(False).all())
        gate.attrs["core_source_specific_bound_pass"] = bool(core["source_specific_bound_pass"].fillna(False).all())
        gate.attrs["core_source_specific_false_cert_pass"] = bool(core["source_specific_false_certificate_conditional_pass_le_05"].fillna(False).all())
        info = core[core["clear_source_certificate_informativeness_pass_ge_70"].notna()]
        gate.attrs["clear_source_certificate_informativeness_pass"] = bool(info["clear_source_certificate_informativeness_pass_ge_70"].all()) if len(info) else False
        if mode == "full":
            dr = gate[gate["scenario"].isin(["stress_outcome_misspec", "stress_ratio_misspec"])]
            gate.attrs["dr_one_nuisance_misspec_source_upper_coverage_pass"] = bool(dr["source_specific_upper_coverage_pass"].all()) if len(dr) == 2 else False
    return gate

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "calibration", "full"], required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--stress-reps", type=int, default=500)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--bootstrap-draws", type=int, default=300)
    ap.add_argument("--epsilon", type=float, default=EPSILON_DEFAULT)
    ap.add_argument("--seed-base", type=int, default=20260827)
    return ap.parse_args()


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    scenarios = scenario_from_args(args)
    scenario_df = pd.DataFrame([asdict(s) for s in scenarios])
    scenario_df.to_csv(outdir / "p1_scenarios.csv", index=False)

    protocol = {
        "mode": args.mode,
        "alpha": ALPHA,
        "epsilon": args.epsilon,
        "budgets": list(BUDGETS_DEFAULT),
        "candidate_models": M,
        "covariates": P,
        "outcome": "continuous Gaussian primary validity DGP; exact analytic target truth",
        "treatment_propensity": PROPENSITY,
        "bootstrap": "Global two-sided Gaussian max-t plus source-specific one-sided Gaussian max-t",
        "source_split": [0.30, 0.20, 0.50],
        "target_split": [0.25, 0.75],
        "tau_scale_by_separation": TAU_SCALE,
        "calibration_coverage_gate": [0.90, 0.99],
        "full_coverage_gate": [0.93, 0.97],
        "portability_bound_min_full": 0.93,
        "false_certificate_conditional_gate": 0.05,
        "clear_source_certificate_gate": 0.70,
        "p1b1_amendment": "Primary certificate uses only independently preselected source-winner contrasts across budgets; global confidence set retained as secondary.",
        "seed_base": args.seed_base,
        "bootstrap_draws": args.bootstrap_draws,
    }
    (outdir / "p1_protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")

    partial_dir = outdir / "partial"
    partial_dir.mkdir(exist_ok=True)
    rows = []
    global_task_id = 0

    def decorate(res, task_id, s, rep, seed):
        res.update({"task_id": task_id, "scenario": s.name, "rep": rep, "seed": seed})
        return res

    total_expected = int(sum(s.reps for s in scenarios))
    total_done = 0
    print(f"Mode={args.mode} scenarios={len(scenarios)} repetitions={total_expected} workers={args.workers}")

    for sidx, s in enumerate(scenarios):
        pfile = partial_dir / f"{s.name}.csv"
        existing = pd.DataFrame()
        done_reps = set()
        if pfile.exists():
            try:
                existing = pd.read_csv(pfile)
                done_reps = set(existing["rep"].astype(int).tolist())
            except Exception:
                existing = pd.DataFrame()
                done_reps = set()
        if len(done_reps) >= s.reps:
            keep = existing[existing["rep"].astype(int) < s.reps].copy()
            rows.extend(keep.to_dict("records"))
            total_done += len(keep)
            global_task_id += s.reps
            print(f"SKIP {s.name}: {len(keep)}/{s.reps} reps already complete")
            continue

        scenario_rows = existing[existing["rep"].astype(int) < s.reps].to_dict("records") if len(existing) else []
        tasks = []
        for rep in range(s.reps):
            tid = global_task_id + rep
            if rep in done_reps:
                continue
            seed = args.seed_base + sidx * 1_000_000 + rep
            tasks.append((tid, seed, rep))
        print(f"RUN {s.name}: remaining={len(tasks)} completed={len(done_reps)}")

        checkpoint_every = max(10, max(1, s.reps // 20))
        completed_since_save = 0
        if args.workers <= 1:
            for tid, seed, rep in tasks:
                res = one_rep(seed, s, BUDGETS_DEFAULT, args.epsilon, args.bootstrap_draws)
                scenario_rows.append(decorate(res, tid, s, rep, seed))
                completed_since_save += 1
                if completed_since_save >= checkpoint_every:
                    pd.DataFrame(scenario_rows).sort_values("rep").to_csv(pfile, index=False)
                    completed_since_save = 0
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                futs = {
                    ex.submit(one_rep, seed, s, BUDGETS_DEFAULT, args.epsilon, args.bootstrap_draws): (tid, seed, rep)
                    for tid, seed, rep in tasks
                }
                for fut in as_completed(futs):
                    tid, seed, rep = futs[fut]
                    res = fut.result()
                    scenario_rows.append(decorate(res, tid, s, rep, seed))
                    completed_since_save += 1
                    if completed_since_save >= checkpoint_every:
                        pd.DataFrame(scenario_rows).sort_values("rep").to_csv(pfile, index=False)
                        completed_since_save = 0
        scenario_df_out = pd.DataFrame(scenario_rows).sort_values("rep")
        scenario_df_out.to_csv(pfile, index=False)
        rows.extend(scenario_df_out.to_dict("records"))
        total_done += len(scenario_df_out)
        global_task_id += s.reps
        print(f"DONE {s.name}: {len(scenario_df_out)}/{s.reps}; cumulative={total_done}/{total_expected}")

    raw = pd.DataFrame(rows).sort_values("task_id").reset_index(drop=True)
    raw.to_csv(outdir / "p1_replication_results.csv", index=False)
    summary = summarize(raw, scenario_df)
    summary.to_csv(outdir / "p1_scenario_summary.csv", index=False)
    gate = make_gate(summary, args.mode)
    gate.to_csv(outdir / "p1_gate.csv", index=False)

    print("\n=== P1 SUMMARY ===")
    cols = [
        "scenario", "simultaneous_pairwise_coverage", "source_specific_contrast_upper_coverage",
        "source_specific_bound_all_budgets_coverage", "mean_confidence_set_size", "singleton_rate",
        "source_specific_certificate_rate", "source_specific_false_certificate_rate_unconditional",
        "source_specific_false_certificate_rate_conditional", "forced_unsafe_rate", "estimated_ess_ratio",
    ]
    print(summary[cols].to_string(index=False))
    if args.mode != "smoke":
        print("\n=== P1 GATE ===")
        print(gate.to_string(index=False))
        print("Gate attrs:", gate.attrs)
    print(f"\nFinished. Results: {outdir.resolve()}")


if __name__ == "__main__":
    main()
