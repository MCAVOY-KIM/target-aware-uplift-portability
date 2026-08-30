from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

EXPECTED_R1_SHA256 = "1c7fe26cebf45f9215c7ec8de54f06ec2e72eb8e72744b3fb2a8d392ae0f3e0e"
FEATURES = [f"f{i}" for i in range(12)]
BUDGETS = (0.10, 0.30, 0.50)
PROPENSITY = 0.85

# Fresh, predeclared tie-breaking stream. Same U across models gives common random numbers
# and introduces no outcome information.
TIE_SEED = np.uint64(2026082806)
RAND_AUDIT_TRAIN_SEED = np.uint64(2026082807)
RAND_AUDIT_TEST_SEED = np.uint64(2026082808)
AUDIT_SUBSAMPLE_N = 500_000


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_r1_module(path: Path):
    sha = sha256_file(path)
    if sha != EXPECTED_R1_SHA256:
        raise RuntimeError(
            f"Frozen R1 source hash mismatch. Expected {EXPECTED_R1_SHA256}, got {sha}."
        )
    spec = importlib.util.spec_from_file_location("r1_frozen", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod, sha


def collect_source_train_select(r1, data_path: Path, frozen, shift_row, chunksize: int):
    Xtr, atr, ytr, itr, ztr = [], [], [], [], []
    Xsel, asel, ysel, isel, zsel = [], [], [], [], []
    total = 0

    usecols = FEATURES + ["treatment", "visit"]
    for ci, df in enumerate(pd.read_csv(data_path, compression="gzip", usecols=usecols, chunksize=chunksize)):
        n = len(df)
        idx = np.arange(total, total+n, dtype=np.uint64)
        X = df[FEATURES].to_numpy(np.float32, copy=False)
        z = r1.pc1_z(X.astype(np.float64, copy=False), frozen)
        p = r1.p_target_from_z(z, shift_row)

        is_target = r1.splitmix64_uniform(idx, r1.MEMBERSHIP_SEED) < p
        is_source = ~is_target
        u_role = r1.splitmix64_uniform(idx, r1.ROLE_SEED)
        tr = is_source & (u_role < 0.30)
        se = is_source & (u_role >= 0.30) & (u_role < 0.50)

        if np.any(tr):
            a = df["treatment"].to_numpy(np.float32, copy=False)[tr]
            y = df["visit"].to_numpy(np.float32, copy=False)[tr]
            Xtr.append(X[tr].copy()); atr.append(a.copy()); ytr.append(y.copy())
            itr.append(idx[tr].astype(np.uint64)); ztr.append(z[tr].astype(np.float64))
        if np.any(se):
            a = df["treatment"].to_numpy(np.float32, copy=False)[se]
            y = df["visit"].to_numpy(np.float32, copy=False)[se]
            Xsel.append(X[se].copy()); asel.append(a.copy()); ysel.append(y.copy())
            isel.append(idx[se].astype(np.uint64)); zsel.append(z[se].astype(np.float64))

        total += n
        print(f"  [{shift_row['label']}] chunk={ci+1} rows={total:,}")

    return (
        np.vstack(Xtr), np.concatenate(atr), np.concatenate(ytr), np.concatenate(itr), np.concatenate(ztr),
        np.vstack(Xsel), np.concatenate(asel), np.concatenate(ysel), np.concatenate(isel), np.concatenate(zsel),
    )


def fit_lexicographic_topq_rule(r1, scores: np.ndarray, row_idx: np.ndarray, q: float):
    """
    Exact top-q on the calibration sample using lexicographic ranking:
      1) larger model score;
      2) among exact score ties, smaller independent hash U.
    This is equivalent to randomized tie-breaking with a frozen exogenous U.
    """
    scores = np.asarray(scores, dtype=np.float64)
    n = len(scores)
    k = int(round(q * n))
    if k <= 0 or k >= n:
        raise ValueError("q produced degenerate k")

    # kth largest observed score.
    c = float(np.partition(scores, n-k)[n-k])
    gt = scores > c
    eq = scores == c
    n_gt = int(gt.sum())
    need = int(k - n_gt)
    n_eq = int(eq.sum())
    if not (0 <= need <= n_eq):
        raise RuntimeError("Invalid tie requirement")

    u_all = r1.splitmix64_uniform(row_idx, TIE_SEED)
    if need == 0:
        u_cut = -1.0
    elif need == n_eq:
        u_cut = 1.0
    else:
        u_eq = u_all[eq]
        u_cut = float(np.partition(u_eq, need-1)[need-1])

    policy = gt | (eq & (u_all <= u_cut))
    treated = int(policy.sum())
    if treated != k:
        raise RuntimeError(f"Exact budget failed: expected {k}, got {treated}")

    return {
        "score_cut": c,
        "tie_u_cut": u_cut,
        "n_gt": n_gt,
        "n_eq": n_eq,
        "n_tie_selected": need,
        "tie_fraction_selected": float(need/n_eq) if n_eq else 0.0,
        "train_policy_rate": float(treated/n),
    }


def apply_rule(r1, scores: np.ndarray, row_idx: np.ndarray, rule: Dict):
    u = r1.splitmix64_uniform(row_idx, TIE_SEED)
    scores = np.asarray(scores, dtype=np.float64)
    return (scores > rule["score_cut"]) | (
        (scores == rule["score_cut"]) & (u <= rule["tie_u_cut"])
    )


def source_ipw(policy, a, y, e=PROPENSITY):
    p = policy.astype(np.float64)
    a = a.astype(np.float64)
    y = y.astype(np.float64)
    psi = p * (a/e*y - (1-a)/(1-e)*y)
    return float(psi.mean()), float(psi.std(ddof=1)/math.sqrt(len(psi)))


def smd_max(X: np.ndarray, a: np.ndarray):
    a = a.astype(bool)
    x1 = X[a].astype(np.float64)
    x0 = X[~a].astype(np.float64)
    m1, m0 = x1.mean(0), x0.mean(0)
    v1, v0 = x1.var(0), x0.var(0)
    pooled = np.sqrt(np.maximum((v1+v0)/2.0, 1e-16))
    smd = (m1-m0)/pooled
    j = int(np.argmax(np.abs(smd)))
    return float(np.max(np.abs(smd))), FEATURES[j], smd


def pc1_decile_audit(z: np.ndarray, a: np.ndarray):
    cuts = np.quantile(z, np.linspace(0,1,11))
    # ensure endpoint inclusion and stable binning
    bins = np.searchsorted(cuts[1:-1], z, side="right")
    overall = float(a.mean())
    rows = []
    for d in range(10):
        m = bins == d
        rows.append({
            "decile": d+1,
            "n": int(m.sum()),
            "treatment_rate": float(a[m].mean()),
            "abs_dev_from_overall": float(abs(a[m].mean()-overall)),
        })
    return pd.DataFrame(rows), float(max(r["abs_dev_from_overall"] for r in rows))


def deterministic_subsample(r1, row_idx: np.ndarray, n: int, seed: np.uint64):
    if len(row_idx) <= n:
        return np.arange(len(row_idx))
    u = r1.splitmix64_uniform(row_idx, seed)
    return np.argpartition(u, n)[:n]


def treatment_predictability_auc(r1, Xtr, atr, itr, Xte, ate, ite):
    ii = deterministic_subsample(r1, itr, AUDIT_SUBSAMPLE_N, RAND_AUDIT_TRAIN_SEED)
    jj = deterministic_subsample(r1, ite, AUDIT_SUBSAMPLE_N, RAND_AUDIT_TEST_SEED)
    model = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, solver="lbfgs", max_iter=150, random_state=20260828)),
    ])
    model.fit(Xtr[ii].astype(np.float64), atr[ii])
    pred = model.predict_proba(Xte[jj].astype(np.float64))[:,1]
    return float(roc_auc_score(ate[jj], pred)), int(len(ii)), int(len(jj))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--r0-outdir", required=True)
    ap.add_argument("--r01-outdir", required=True)
    ap.add_argument("--r1-source", required=True)
    ap.add_argument("--r1-outdir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--chunksize", type=int, default=500_000)
    args = ap.parse_args()

    data = Path(args.data).resolve()
    r0 = Path(args.r0_outdir).resolve()
    r01 = Path(args.r01_outdir).resolve()
    r1out = Path(args.r1_outdir).resolve()
    out = Path(args.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    print("R1.1-1 Verify frozen R1 source/models...")
    r1, r1sha = load_r1_module(Path(args.r1_source).resolve())
    frozen = r1.load_frozen_shift(r0, r01)
    shifts = frozen["shifts"]

    model_files = sorted((r1out/"models").rglob("*.joblib"))
    if len(model_files) != 18:
        raise RuntimeError(f"Expected 18 frozen model artifacts, found {len(model_files)}")
    manifest = []
    for p in model_files:
        joblib.load(p)
        manifest.append({
            "file": str(p.relative_to(r1out)),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        })
    pd.DataFrame(manifest).to_csv(out/"criteo_r11_model_manifest.csv", index=False)

    old_winners = pd.read_csv(r1out/"criteo_r1_source_winners.csv")
    selection_rows, winner_rows, audit_rows, decile_rows = [], [], [], []

    for _, shift in shifts.iterrows():
        name = str(shift["label"])
        print(f"\nR1.1-2 Rebuild frozen source train/select for {name}...")
        (
            Xtr, atr, ytr, itr, ztr,
            Xsel, asel, ysel, isel, zsel,
        ) = collect_source_train_select(r1, data, frozen, shift, args.chunksize)

        # Randomization audit before any corrected winner is used.
        max_smd, max_smd_feature, _ = smd_max(Xtr, atr)
        dec, max_decile_dev = pc1_decile_audit(ztr, atr)
        dec.insert(0, "scenario", name)
        decile_rows.extend(dec.to_dict("records"))
        auc, auc_n_train, auc_n_test = treatment_predictability_auc(
            r1, Xtr, atr, itr, Xsel, asel, isel
        )
        audit_rows.append({
            "scenario": name,
            "source_train_n": len(Xtr),
            "source_select_n": len(Xsel),
            "source_train_treatment_rate": float(atr.mean()),
            "source_select_treatment_rate": float(asel.mean()),
            "max_abs_feature_smd_treated_vs_control": max_smd,
            "max_abs_feature_smd_feature": max_smd_feature,
            "max_pc1_decile_treatment_rate_dev_from_overall": max_decile_dev,
            "treatment_predictability_auc_on_source_select": auc,
            "auc_train_n": auc_n_train,
            "auc_test_n": auc_n_test,
        })

        scenario_selection = []
        for model_name in r1.MODEL_NAMES:
            bundle = joblib.load(r1out/"models"/name/f"{model_name}.joblib")
            score_tr = r1.predict_tau(bundle, Xtr.astype(np.float64, copy=False))
            score_sel = r1.predict_tau(bundle, Xsel.astype(np.float64, copy=False))

            for q in BUDGETS:
                rule = fit_lexicographic_topq_rule(r1, score_tr, itr, q)
                pol_sel = apply_rule(r1, score_sel, isel, rule)
                gain, se = source_ipw(pol_sel, asel, ysel)
                row = {
                    "scenario": name,
                    "budget": q,
                    "model": model_name,
                    "score_cut": rule["score_cut"],
                    "tie_u_cut": rule["tie_u_cut"],
                    "train_policy_rate": rule["train_policy_rate"],
                    "source_select_policy_rate": float(pol_sel.mean()),
                    "select_abs_budget_deviation": float(abs(pol_sel.mean()-q)),
                    "threshold_tie_count_train": rule["n_eq"],
                    "threshold_tie_fraction_train": float(rule["n_eq"]/len(score_tr)),
                    "tie_fraction_selected": rule["tie_fraction_selected"],
                    "source_select_ipw_gain": gain,
                    "source_select_ipw_se": se,
                }
                selection_rows.append(row)
                scenario_selection.append(row)

        temp = pd.DataFrame(scenario_selection)
        for q in BUDGETS:
            g = temp[temp["budget"]==q].sort_values(
                ["source_select_ipw_gain","model"], ascending=[False,True]
            )
            b, s = g.iloc[0], g.iloc[1]
            old = old_winners[(old_winners.scenario==name)&(old_winners.budget==q)].iloc[0]
            winner_rows.append({
                "scenario": name,
                "budget": q,
                "corrected_source_winner": b["model"],
                "winner_ipw_gain": float(b["source_select_ipw_gain"]),
                "runner_up": s["model"],
                "runner_up_ipw_gain": float(s["source_select_ipw_gain"]),
                "winner_minus_runner_up": float(b["source_select_ipw_gain"]-s["source_select_ipw_gain"]),
                "original_r1_winner": old["source_winner"],
                "winner_changed_after_budget_fix": bool(b["model"] != old["source_winner"]),
            })

        del Xtr, atr, ytr, itr, ztr, Xsel, asel, ysel, isel, zsel

    selection = pd.DataFrame(selection_rows)
    winners = pd.DataFrame(winner_rows)
    audits = pd.DataFrame(audit_rows)
    deciles = pd.DataFrame(decile_rows)

    selection.to_csv(out/"criteo_r11_budget_corrected_source_selection.csv", index=False)
    winners.to_csv(out/"criteo_r11_corrected_source_winners.csv", index=False)
    audits.to_csv(out/"criteo_r11_randomization_audit.csv", index=False)
    deciles.to_csv(out/"criteo_r11_pc1_decile_treatment_audit.csv", index=False)

    gates = []
    for name in audits.scenario:
        a = audits[audits.scenario==name].iloc[0]
        s = selection[selection.scenario==name]
        gates.append({
            "scenario": name,
            "all_train_budgets_exact": bool(np.all(np.abs(s.train_policy_rate-s.budget) <= 1e-6)),
            "all_select_budget_rates_within_005": bool(np.all(s.select_abs_budget_deviation <= .005)),
            "max_feature_smd_pass_le_02": bool(a.max_abs_feature_smd_treated_vs_control <= .02),
            "pc1_decile_randomization_pass_dev_le_005": bool(a.max_pc1_decile_treatment_rate_dev_from_overall <= .005),
            "treatment_predictability_auc_pass_le_51": bool(a.treatment_predictability_auc_on_source_select <= .51),
            "all_selection_finite": bool(np.isfinite(s.source_select_ipw_gain).all()),
            "frozen_models_load_pass": True,
            "target_outcomes_used": False,
            "source_infer_outcomes_used": False,
        })
    gate = pd.DataFrame(gates)
    gate.to_csv(out/"criteo_r11_gate.csv", index=False)

    protocol = {
        "stage": "Criteo R1.1 Budget Fidelity and Randomization Audit",
        "frozen_r1_source_sha256": r1sha,
        "tie_seed": int(TIE_SEED),
        "tie_rule": "lexicographic top-q: score descending, independent row-hash U ascending among exact score ties",
        "budgets": list(BUDGETS),
        "propensity_used_for_source_selection": PROPENSITY,
        "target_outcomes_used": False,
        "source_infer_outcomes_used": False,
        "randomization_gates": {
            "max_abs_feature_smd": .02,
            "max_pc1_decile_rate_deviation": .005,
            "treatment_prediction_auc": .51,
        },
        "budget_gate": {
            "train_exact": True,
            "source_select_abs_deviation": .005,
        },
    }
    (out/"criteo_r11_protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")

    summary = {
        "stage": "Criteo R1.1 Budget Fidelity and Randomization Audit",
        "all_gate_pass": bool(gate.drop(columns=["scenario"]).all(axis=None)),
        "winner_changes": int(winners.winner_changed_after_budget_fix.sum()),
        "max_original_budget_violation_observed_in_r1": 0.4560388,
        "target_outcomes_used": False,
        "source_infer_outcomes_used": False,
        "next_if_pass": "Freeze corrected source winners and lexicographic tie rule; proceed R2.",
    }
    (out/"criteo_r11_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== R1.1 RANDOMIZATION AUDIT ===")
    print(audits.to_string(index=False))
    print("\n=== R1.1 CORRECTED SOURCE WINNERS ===")
    print(winners.to_string(index=False))
    print("\n=== R1.1 GATE ===")
    print(gate.to_string(index=False))
    print("\nSummary:", summary)
    print("\nFinished. Results:", out)


if __name__ == "__main__":
    main()
