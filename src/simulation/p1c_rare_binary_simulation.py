
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import log_ndtr
from scipy.stats import norm, multivariate_normal

ALPHA = 0.05
P = 10
M = 6
BUDGETS_DEFAULT = (0.10, 0.30, 0.50)
EPSILON_DEFAULT = 0.005

# Criteo-like binary stress: ~4.68% source marginal visit rate and 85/15 treatment split.
PROPENSITY = 0.85
CONTROL_RATE_SOURCE = 0.040
TREATED_RATE_SOURCE = 0.048
HET_SCALE = 0.50
RIDGE = 1e-6

# Probit baseline and heterogeneous treatment-response coefficients.
BETA0 = np.zeros(P)
BETA0[3] = 0.35
BETA0[4] = -0.25
BETA_HET = np.zeros(P)
BETA_HET[0] = 0.35
BETA_HET[1] = 0.25
BETA_HET[2] = 0.15
BETA1 = BETA0 + HET_SCALE * BETA_HET

def calibrate_probit_intercept(rate: float, beta: np.ndarray) -> float:
    # If X~N(0,I), E Phi(alpha + beta'X) = Phi(alpha / sqrt(1+||beta||^2)).
    return float(norm.ppf(rate) * math.sqrt(1.0 + float(beta @ beta)))

ALPHA0 = calibrate_probit_intercept(CONTROL_RATE_SOURCE, BETA0)
ALPHA1 = calibrate_probit_intercept(TREATED_RATE_SOURCE, BETA1)

# Pretrained score prototypes. Near = almost indistinguishable ranking rules; clear = diverse rules.
_PROTOS = np.zeros((M, P))
_PROTOS[0, 0] = 1.0
_PROTOS[1, 1] = 1.0
_PROTOS[2, 0] = 1.0; _PROTOS[2, 1] = 1.0
_PROTOS[3, 2] = 1.0
_PROTOS[4, 0] = 1.0; _PROTOS[4, 1] = -1.0
_PROTOS[5, 0] = -1.0
_BASE = _PROTOS[2] / np.linalg.norm(_PROTOS[2])
SEP_BLEND = {"near": 0.08, "moderate": 0.40, "clear": 0.95}
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
    return v.copy() if n < 1e-12 else v / n


def candidate_library(separation: str) -> np.ndarray:
    s = SEP_BLEND[separation]
    rows = []
    for proto in _PROTOS:
        v = normalize(proto)
        w = (1.0 - s) * _BASE + s * v
        rows.append(normalize(v if np.linalg.norm(w) < 1e-10 else w))
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


def p0_true(x: np.ndarray) -> np.ndarray:
    return norm.cdf(ALPHA0 + x @ BETA0)


def p1_true(x: np.ndarray) -> np.ndarray:
    return norm.cdf(ALPHA1 + x @ BETA1)


def make_data(n: int, delta: np.ndarray, rng: np.random.Generator, with_outcome: bool) -> Dict[str, np.ndarray]:
    x = rng.normal(size=(n, P)) + delta
    out = {"x": x}
    if with_outcome:
        a = rng.binomial(1, PROPENSITY, size=n).astype(float)
        p = np.where(a == 1.0, p1_true(x), p0_true(x))
        y = rng.binomial(1, p, size=n).astype(float)
        out.update({"a": a, "y": y})
    return out


def outcome_design(x: np.ndarray, correct: bool) -> np.ndarray:
    if correct:
        return np.column_stack([np.ones(len(x)), x])
    # Deliberately omit effect modifiers X1-X3, while retaining baseline prognostic variables.
    return np.column_stack([np.ones(len(x)), x[:, 3:]])


def _probit_nll_grad(theta: np.ndarray, z: np.ndarray, y: np.ndarray) -> Tuple[float, np.ndarray]:
    eta = np.clip(z @ theta, -12.0, 12.0)
    logphi = -0.5 * eta * eta - 0.5 * math.log(2.0 * math.pi)
    logp = log_ndtr(eta)
    log1mp = log_ndtr(-eta)
    ll = y * logp + (1.0 - y) * log1mp
    # d loglik / d eta.
    score_eta = y * np.exp(logphi - logp) - (1.0 - y) * np.exp(logphi - log1mp)
    nll = -float(np.sum(ll)) + 0.5 * RIDGE * float(theta @ theta)
    grad = -(z.T @ score_eta) + RIDGE * theta
    return nll, grad


def _fit_probit(z: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, bool]:
    rate = float((y.sum() + 0.5) / (len(y) + 1.0))
    theta0 = np.zeros(z.shape[1])
    theta0[0] = float(norm.ppf(np.clip(rate, 1e-5, 1.0 - 1e-5)))
    res = minimize(
        lambda th: _probit_nll_grad(th, z, y),
        theta0,
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": 120, "ftol": 1e-10, "gtol": 1e-6},
    )
    theta = res.x if np.all(np.isfinite(res.x)) else theta0
    return theta, bool(res.success and np.all(np.isfinite(theta)))


def fit_outcome_nuisance(train: Dict[str, np.ndarray], misspecified: bool):
    x, a, y = train["x"], train["a"], train["y"]
    correct = not misspecified
    z = outcome_design(x, correct)
    coefs = []
    success = []
    arm_event_counts = []
    arm_sizes = []
    for arm in (0.0, 1.0):
        mask = a == arm
        theta, ok = _fit_probit(z[mask], y[mask])
        coefs.append(theta)
        success.append(ok)
        arm_event_counts.append(int(y[mask].sum()))
        arm_sizes.append(int(mask.sum()))
    return coefs[0], coefs[1], correct, bool(all(success)), tuple(arm_event_counts), tuple(arm_sizes)


def predict_mu(x: np.ndarray, nuisance) -> Tuple[np.ndarray, np.ndarray]:
    c0, c1, correct, *_ = nuisance
    z = outcome_design(x, correct)
    p0 = norm.cdf(np.clip(z @ c0, -12.0, 12.0))
    p1 = norm.cdf(np.clip(z @ c1, -12.0, 12.0))
    return np.clip(p0, 1e-6, 1.0 - 1e-6), np.clip(p1, 1e-6, 1.0 - 1e-6)


def fit_ratio_delta(source_train_x: np.ndarray, target_adapt_x: np.ndarray, misspecified: bool) -> np.ndarray:
    d = target_adapt_x.mean(axis=0) - source_train_x.mean(axis=0)
    if misspecified:
        d = 0.50 * d
    return d


def ratio_normal_shift(x: np.ndarray, delta_hat: np.ndarray) -> np.ndarray:
    logw = x @ delta_hat - 0.5 * float(delta_hat @ delta_hat)
    return np.exp(np.clip(logw, -30.0, 30.0))


def score_matrix(x: np.ndarray, W: np.ndarray) -> np.ndarray:
    return x @ W.T


def thresholds_from_sample(scores: np.ndarray, budgets: Tuple[float, ...]) -> np.ndarray:
    th = np.empty((len(budgets), M))
    for qi, q in enumerate(budgets):
        th[qi] = np.quantile(scores, 1.0 - q, axis=0)
    return th


def policy_tensor(scores: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
    return scores[:, None, :] >= thresholds[None, :, :]


def exact_arm_policy_probability(alpha: float, beta: np.ndarray, w: np.ndarray, threshold: float, delta: np.ndarray) -> float:
    """
    Exact E[Phi(alpha + beta'X) * 1{w'X >= threshold}], X~N(delta,I).
    Introduce E~N(0,1) independent and use a bivariate Gaussian tail probability.
    """
    scale = float(np.linalg.norm(w))
    if scale < 1e-12:
        return 0.0
    u = w / scale
    a = threshold / scale - float(u @ delta)
    mu_r = float(alpha + beta @ delta)
    sd_r = math.sqrt(1.0 + float(beta @ beta))
    b = -mu_r / sd_r
    rho = float(np.clip((u @ beta) / sd_r, -0.999999, 0.999999))
    lower_cdf = float(multivariate_normal.cdf([a, b], mean=[0.0, 0.0], cov=[[1.0, rho], [rho, 1.0]]))
    val = 1.0 - float(norm.cdf(a)) - float(norm.cdf(b)) + lower_cdf
    return float(np.clip(val, 0.0, 1.0))


def exact_gain_probit_policy(w: np.ndarray, threshold: float, delta: np.ndarray) -> float:
    return exact_arm_policy_probability(ALPHA1, BETA1, w, threshold, delta) - exact_arm_policy_probability(ALPHA0, BETA0, w, threshold, delta)


def exact_gains(W: np.ndarray, thresholds: np.ndarray, delta: np.ndarray) -> np.ndarray:
    Q = thresholds.shape[0]
    g = np.empty((Q, M))
    for qi in range(Q):
        for m in range(M):
            g[qi, m] = exact_gain_probit_policy(W[m], thresholds[qi, m], delta)
    return g


def source_select_winners(source_train, source_select, W, budgets, outcome_nuisance) -> np.ndarray:
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
    corr = nearest_psd_corr(cov / np.outer(se, se))
    vals, vecs = np.linalg.eigh(corr)
    L = vecs @ np.diag(np.sqrt(np.clip(vals, 0.0, None)))
    z = rng.normal(size=(draws, len(se))) @ L.T
    return float(np.quantile(np.max(np.abs(z), axis=1), 1.0 - alpha))


def gaussian_one_sided_max_t_critical(cov: np.ndarray, alpha: float, draws: int, rng: np.random.Generator) -> float:
    se = np.sqrt(np.clip(np.diag(cov), 1e-16, None))
    corr = nearest_psd_corr(cov / np.outer(se, se))
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
            L[qi, j, m], U[qi, j, m] = pair_l[k], pair_u[k]
            L[qi, m, j], U[qi, m, j] = -pair_u[k], -pair_l[k]
            k += 1
    return L, U


def one_rep(seed: int, scenario: Scenario, budgets: Tuple[float, ...], epsilon: float, bootstrap_draws: int) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    W = candidate_library(scenario.separation)
    delta = target_delta(scenario.ess_target, scenario.shift_relevance)

    ns_tr = int(round(scenario.n_source * 0.30))
    ns_sel = int(round(scenario.n_source * 0.20))
    ns_inf = scenario.n_source - ns_tr - ns_sel
    nt_ad = int(round(scenario.n_target * 0.25))
    nt_inf = scenario.n_target - nt_ad

    source_train = make_data(ns_tr, np.zeros(P), rng, True)
    source_select = make_data(ns_sel, np.zeros(P), rng, True)
    source_infer = make_data(ns_inf, np.zeros(P), rng, True)
    target_adapt = make_data(nt_ad, delta, rng, False)
    target_infer = make_data(nt_inf, delta, rng, False)

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

    plugin = (pi_t * mudiff_t[:, None, None]).mean(axis=0)
    aug = (pi_s * (r_s * resid_s)[:, None, None]).mean(axis=0)
    ghat = plugin + aug

    phi_t_models = pi_t * mudiff_t[:, None, None]
    phi_s_models = pi_s * (r_s * resid_s)[:, None, None]
    phi_t_models -= phi_t_models.mean(axis=0, keepdims=True)
    phi_s_models -= phi_s_models.mean(axis=0, keepdims=True)

    true_g = exact_gains(W, target_th, delta)
    Q = len(budgets)

    est_pairs, true_pairs, pair_t_cols, pair_s_cols = [], [], [], []
    for qi in range(Q):
        for j, m in PAIR_INDEX:
            est_pairs.append(ghat[qi, j] - ghat[qi, m])
            true_pairs.append(true_g[qi, j] - true_g[qi, m])
            pair_t_cols.append(phi_t_models[:, qi, j] - phi_t_models[:, qi, m])
            pair_s_cols.append(phi_s_models[:, qi, j] - phi_s_models[:, qi, m])
    est_pairs, true_pairs = np.asarray(est_pairs), np.asarray(true_pairs)
    XT, XS = np.column_stack(pair_t_cols), np.column_stack(pair_s_cols)
    cov = (XT.T @ XT) / (nt_inf * max(nt_inf - 1, 1)) + (XS.T @ XS) / (ns_inf * max(ns_inf - 1, 1))
    se = np.sqrt(np.clip(np.diag(cov), 1e-16, None))
    crit = gaussian_max_t_critical(cov, ALPHA, bootstrap_draws, rng)
    lower, upper = est_pairs - crit * se, est_pairs + crit * se
    simultaneous_coverage = float(np.all((true_pairs >= lower) & (true_pairs <= upper)))
    L, U = build_ordered_bounds(lower, upper, Q)

    src_est, src_true, src_t_cols, src_s_cols, src_meta = [], [], [], [], []
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
    src_est, src_true = np.asarray(src_est), np.asarray(src_true)
    XTs, XSs = np.column_stack(src_t_cols), np.column_stack(src_s_cols)
    cov_src = (XTs.T @ XTs) / (nt_inf * max(nt_inf - 1, 1)) + (XSs.T @ XSs) / (ns_inf * max(ns_inf - 1, 1))
    se_src = np.sqrt(np.clip(np.diag(cov_src), 1e-16, None))
    crit_src = gaussian_one_sided_max_t_critical(cov_src, ALPHA, bootstrap_draws, rng)
    upper_src = src_est + crit_src * se_src
    source_upper_coverage = float(np.all(src_true <= upper_src))

    source_specific_bounds = np.zeros(Q)
    for qi in range(Q):
        vals = [upper_src[k] for k, meta in enumerate(src_meta) if meta[0] == qi]
        source_specific_bounds[qi] = float(max(0.0, np.max(vals)))

    set_sizes, set_best_covered = [], []
    source_specific_bound_covered, source_specific_certified, source_specific_false_cert = [], [], []
    forced_unsafe, forced_regret, source_true_regret = [], [], []

    for qi in range(Q):
        cset = [m for m in range(M) if np.all(L[qi, :, m] <= 1e-15)]
        set_sizes.append(len(cset))
        best = int(np.argmax(true_g[qi]))
        set_best_covered.append(float(best in cset))

        ms = int(source_winner[qi])
        true_regret_s = float(np.max(true_g[qi]) - true_g[qi, ms])
        bound_ss = float(source_specific_bounds[qi])
        source_true_regret.append(true_regret_s)
        source_specific_bound_covered.append(float(true_regret_s <= bound_ss + 1e-12))
        cert_ss = bool(bound_ss <= epsilon)
        source_specific_certified.append(float(cert_ss))
        source_specific_false_cert.append(float(cert_ss and true_regret_s > epsilon))

        mf = int(np.argmax(ghat[qi]))
        regf = float(np.max(true_g[qi]) - true_g[qi, mf])
        forced_regret.append(regf)
        forced_unsafe.append(float(regf > epsilon))

    true_ess = math.exp(-float(delta @ delta))
    est_ess = float((r_s.sum() ** 2) / (len(r_s) * np.sum(r_s ** 2)))
    any_false_certificate = float(any(x == 1.0 for x in source_specific_false_cert))
    outcome_fit_success = float(out_nuis[3])
    control_events, treated_events = out_nuis[4]
    control_n, treated_n = out_nuis[5]

    return {
        "simultaneous_pairwise_coverage": simultaneous_coverage,
        "optimal_set_all_budgets_coverage": float(all(x == 1.0 for x in set_best_covered)),
        "source_specific_contrast_upper_coverage": source_upper_coverage,
        "source_specific_bound_all_budgets_coverage": float(all(x == 1.0 for x in source_specific_bound_covered)),
        "source_specific_certificate_rate": float(np.mean(source_specific_certified)),
        "source_specific_false_certificate_rate_unconditional": float(np.mean(source_specific_false_cert)),
        "source_specific_any_false_certificate": any_false_certificate,
        "num_source_specific_certified": int(np.sum(source_specific_certified)),
        "num_source_specific_false_certified": int(np.sum(source_specific_false_cert)),
        "mean_source_specific_portability_bound": float(np.mean(source_specific_bounds)),
        "source_specific_critical_value": float(crit_src),
        "mean_confidence_set_size": float(np.mean(set_sizes)),
        "singleton_rate": float(np.mean(np.asarray(set_sizes) == 1)),
        "forced_unsafe_rate": float(np.mean(forced_unsafe)),
        "mean_forced_regret": float(np.mean(forced_regret)),
        "mean_source_true_regret": float(np.mean(source_true_regret)),
        "true_ess_ratio": float(true_ess),
        "estimated_ess_ratio": est_ess,
        "critical_value": float(crit),
        "outcome_fit_success": outcome_fit_success,
        "control_train_events": float(control_events),
        "treated_train_events": float(treated_events),
        "control_train_n": float(control_n),
        "treated_train_n": float(treated_n),
        "source_train_event_rate": float((control_events + treated_events) / max(control_n + treated_n, 1)),
    }


def core_scenarios(reps: int) -> List[Scenario]:
    out = []
    for n in (20000, 80000):
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
    return [
        Scenario("stress_irrelevant", 80000, 80000, 0.5, "moderate", "irrelevant", "both_correct", reps),
        Scenario("stress_outcome_misspec", 80000, 80000, 0.5, "moderate", "relevant", "outcome_misspecified", reps),
        Scenario("stress_ratio_misspec", 80000, 80000, 0.5, "moderate", "relevant", "ratio_misspecified", reps),
        Scenario("stress_both_misspec", 80000, 80000, 0.5, "moderate", "relevant", "both_misspecified", reps),
    ]


def scenario_from_args(args) -> List[Scenario]:
    if args.mode == "smoke":
        return [
            Scenario("smoke_rare_near", 5000, 5000, 0.5, "near", "relevant", "both_correct", args.reps),
            Scenario("smoke_rare_clear", 5000, 5000, 0.5, "clear", "relevant", "both_correct", args.reps),
            Scenario("smoke_rare_dr", 5000, 5000, 0.5, "moderate", "relevant", "outcome_misspecified", args.reps),
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
        "source_specific_contrast_upper_coverage",
        "source_specific_bound_all_budgets_coverage",
        "source_specific_certificate_rate",
        "source_specific_false_certificate_rate_unconditional",
        "source_specific_any_false_certificate",
        "num_source_specific_certified",
        "num_source_specific_false_certified",
        "mean_source_specific_portability_bound",
        "source_specific_critical_value",
        "mean_confidence_set_size",
        "singleton_rate",
        "forced_unsafe_rate",
        "mean_forced_regret",
        "mean_source_true_regret",
        "true_ess_ratio",
        "estimated_ess_ratio",
        "critical_value",
        "outcome_fit_success",
        "control_train_events",
        "treated_train_events",
        "control_train_n",
        "treated_train_n",
        "source_train_event_rate",
    ]
    rows = []
    for name, g in raw.groupby("scenario", sort=False):
        meta = scenario_df.loc[scenario_df["name"] == name].iloc[0].to_dict()
        row = {"scenario": name}
        row.update({k: meta[k] for k in ["n_source", "n_target", "ess_target", "separation", "shift_relevance", "nuisance", "reps"]})
        for m in metrics:
            row[m] = float(g[m].mean())
            row[m + "_mcse"] = float(g[m].std(ddof=1) / math.sqrt(len(g))) if len(g) > 1 else np.nan
        total_cert = float(g["num_source_specific_certified"].sum())
        total_false = float(g["num_source_specific_false_certified"].sum())
        row["source_specific_false_certificate_rate_conditional"] = (total_false / total_cert) if total_cert > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def make_gate(summary: pd.DataFrame, mode: str) -> pd.DataFrame:
    rows = []
    for _, r in summary.iterrows():
        if mode == "smoke":
            anti_under = bound_pass = fwer_pass = fit_pass = informative = dr_pass = np.nan
        else:
            n = int(r["n_source"])
            # P1-C is a stress gate. Anti-conservatism is the primary failure mode.
            coverage_floor = 0.88 if mode == "calibration" else (0.90 if n == 20000 else 0.92)
            bound_floor = 0.90 if mode == "calibration" else (0.90 if n == 20000 else 0.93)
            anti_under = bool(r["source_specific_contrast_upper_coverage"] >= coverage_floor)
            bound_pass = bool(r["source_specific_bound_all_budgets_coverage"] >= bound_floor)
            fwer_pass = bool(r["source_specific_any_false_certificate"] <= 0.05)
            fit_pass = bool(r["outcome_fit_success"] >= 0.98)
            informative = np.nan
            if r["scenario"].startswith("core_") and r["separation"] == "clear" and n == 80000:
                ess = float(r["ess_target"])
                if abs(ess - 0.8) < 1e-12:
                    informative = bool(r["source_specific_certificate_rate"] >= 0.50)
                elif abs(ess - 0.5) < 1e-12:
                    informative = bool(r["source_specific_certificate_rate"] >= 0.30)
            dr_pass = np.nan
            if r["scenario"] in ("stress_outcome_misspec", "stress_ratio_misspec"):
                dr_pass = bool(r["source_specific_contrast_upper_coverage"] >= 0.92)

        rows.append({
            "scenario": r["scenario"],
            "source_specific_anti_undercoverage_pass": anti_under,
            "source_specific_bound_pass": bound_pass,
            "familywise_false_certificate_pass_le_05": fwer_pass,
            "outcome_fit_success_pass_ge_98": fit_pass,
            "clear_n80000_stress_informativeness_pass": informative,
            "dr_one_nuisance_misspec_coverage_pass_ge_92": dr_pass,
        })
    gate = pd.DataFrame(rows)
    if mode != "smoke":
        core = gate[gate["scenario"].str.startswith("core_")]
        gate.attrs["core_anti_undercoverage_pass"] = bool(core["source_specific_anti_undercoverage_pass"].fillna(False).all())
        gate.attrs["core_bound_pass"] = bool(core["source_specific_bound_pass"].fillna(False).all())
        gate.attrs["core_familywise_false_cert_pass"] = bool(core["familywise_false_certificate_pass_le_05"].fillna(False).all())
        gate.attrs["core_outcome_fit_pass"] = bool(core["outcome_fit_success_pass_ge_98"].fillna(False).all())
        info = core[core["clear_n80000_stress_informativeness_pass"].notna()]
        gate.attrs["clear_n80000_stress_informativeness_pass"] = bool(info["clear_n80000_stress_informativeness_pass"].all()) if len(info) else False
        if mode == "full":
            dr = gate[gate["dr_one_nuisance_misspec_coverage_pass_ge_92"].notna()]
            gate.attrs["dr_one_nuisance_misspec_pass"] = bool(dr["dr_one_nuisance_misspec_coverage_pass_ge_92"].all()) if len(dr) else False
    return gate


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "calibration", "full"], required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--stress-reps", type=int, default=300)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--bootstrap-draws", type=int, default=500)
    ap.add_argument("--epsilon", type=float, default=EPSILON_DEFAULT)
    ap.add_argument("--seed-base", type=int, default=202608272)
    return ap.parse_args()


def run_one_task(payload):
    seed, scenario_dict, budgets, epsilon, bootstrap_draws = payload
    scenario = Scenario(**scenario_dict)
    res = one_rep(seed, scenario, budgets, epsilon, bootstrap_draws)
    res["seed"] = seed
    res["scenario"] = scenario.name
    return res


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    partial_dir = outdir / "partial"
    partial_dir.mkdir(parents=True, exist_ok=True)
    budgets = tuple(BUDGETS_DEFAULT)
    scenarios = scenario_from_args(args)

    scenario_df = pd.DataFrame([asdict(s) for s in scenarios])
    scenario_df.to_csv(outdir / "p1c_scenarios.csv", index=False)

    protocol = {
        "stage": "P1-C Rare-Binary Robustness Gate",
        "method_frozen_from": "P1-B.1",
        "alpha": ALPHA,
        "epsilon": args.epsilon,
        "budgets": budgets,
        "p": P,
        "models": M,
        "treatment_probability": PROPENSITY,
        "source_control_rate": CONTROL_RATE_SOURCE,
        "source_treated_rate": TREATED_RATE_SOURCE,
        "source_marginal_rate": (1-PROPENSITY)*CONTROL_RATE_SOURCE + PROPENSITY*TREATED_RATE_SOURCE,
        "binary_link": "probit",
        "truth": "bivariate-normal analytic integration conditional on empirical target-adapt thresholds",
        "split": {"source_train":0.30,"source_select":0.20,"source_infer":0.50,"target_adapt":0.25,"target_infer":0.75},
        "primary_family": "source-selected model vs 5 competitors across 3 budgets, one-sided simultaneous upper max-t",
        "global_pairwise_family": "secondary only",
        "rare_event_gate_logic": "prioritize anti-undercoverage; conservatism is reported rather than failed unless informativeness collapses",
        "bootstrap_draws": args.bootstrap_draws,
        "seed_base": args.seed_base,
    }
    (outdir / "p1c_protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")

    total_expected = int(sum(s.reps for s in scenarios))
    completed_total = 0
    print(f"Mode={args.mode} scenarios={len(scenarios)} repetitions={total_expected} workers={args.workers}")

    all_parts = []
    for sidx, scenario in enumerate(scenarios):
        part_path = partial_dir / f"{scenario.name}.csv"
        if part_path.exists():
            old = pd.read_csv(part_path)
        else:
            old = pd.DataFrame()
        done = set(old["rep"].astype(int).tolist()) if len(old) and "rep" in old else set()
        remaining = [r for r in range(scenario.reps) if r not in done]
        print(f"RUN {scenario.name}: remaining={len(remaining)} completed={len(done)}")

        new_rows = []
        tasks = []
        for rep in remaining:
            seed = int(args.seed_base + sidx * 10_000_000 + rep)
            tasks.append((seed, asdict(scenario), budgets, args.epsilon, args.bootstrap_draws, rep))

        if tasks:
            if args.workers <= 1:
                for seed, sc, bd, ep, draws, rep in tasks:
                    row = run_one_task((seed, sc, bd, ep, draws))
                    row["rep"] = rep
                    new_rows.append(row)
            else:
                with ProcessPoolExecutor(max_workers=args.workers) as ex:
                    futs = {ex.submit(run_one_task, (seed, sc, bd, ep, draws)): rep for seed, sc, bd, ep, draws, rep in tasks}
                    for fut in as_completed(futs):
                        row = fut.result()
                        row["rep"] = futs[fut]
                        new_rows.append(row)

            new_df = pd.DataFrame(new_rows)
            merged = pd.concat([old, new_df], ignore_index=True)
            merged = merged.sort_values("rep").drop_duplicates("rep", keep="last")
            merged.to_csv(part_path, index=False)
        else:
            merged = old

        all_parts.append(merged)
        completed_total += len(merged)
        print(f"DONE {scenario.name}: {len(merged)}/{scenario.reps}; cumulative={completed_total}/{total_expected}")

    raw = pd.concat(all_parts, ignore_index=True)
    raw.to_csv(outdir / "p1c_replication_results.csv", index=False)
    summary = summarize(raw, scenario_df)
    summary.to_csv(outdir / "p1c_scenario_summary.csv", index=False)
    gate = make_gate(summary, args.mode)
    gate.to_csv(outdir / "p1c_gate.csv", index=False)

    cols = [
        "scenario", "source_specific_contrast_upper_coverage",
        "source_specific_bound_all_budgets_coverage", "source_specific_any_false_certificate",
        "source_specific_certificate_rate", "forced_unsafe_rate",
        "outcome_fit_success", "control_train_events", "source_train_event_rate",
        "estimated_ess_ratio",
    ]
    print("\n=== P1-C SUMMARY ===")
    print(summary[cols].to_string(index=False))
    if args.mode != "smoke":
        print("\n=== P1-C GATE ===")
        print(gate.to_string(index=False))
        print("Gate attrs:", gate.attrs)
    print(f"\nFinished. Results: {outdir}")


if __name__ == "__main__":
    main()
