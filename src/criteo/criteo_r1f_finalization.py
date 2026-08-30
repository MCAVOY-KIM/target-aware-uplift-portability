from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

EXPECTED_R1_SHA256 = "1c7fe26cebf45f9215c7ec8de54f06ec2e72eb8e72744b3fb2a8d392ae0f3e0e"
EXPECTED_R12_SHA256 = "99453d9155046977d73a5687ec1a6ff62103d9e9bee80d1cbf205c2a6fc472ce"
FEATURES = [f"f{i}" for i in range(12)]
BUDGETS = (0.10, 0.30, 0.50)
TIE_SEED = np.uint64(2026082806)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, expected_sha: str, name: str):
    sha = sha256_file(path)
    if sha != expected_sha:
        raise RuntimeError(f"{name} source hash mismatch: expected={expected_sha} got={sha}")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod, sha


def collect_source_train_select(r1, data_path: Path, frozen, shift_row, chunksize: int):
    Xtr, itr = [], []
    Xse, ase, yse, ise = [], [], [], []
    total = 0
    usecols = FEATURES + ["treatment", "visit"]

    for ci, df in enumerate(pd.read_csv(data_path, compression="gzip", usecols=usecols, chunksize=chunksize)):
        n = len(df)
        idx = np.arange(total, total+n, dtype=np.uint64)
        X = df[FEATURES].to_numpy(np.float32, copy=False)
        z = r1.pc1_z(X.astype(np.float64, copy=False), frozen)
        p_t = r1.p_target_from_z(z, shift_row)

        is_target = r1.splitmix64_uniform(idx, r1.MEMBERSHIP_SEED) < p_t
        is_source = ~is_target
        role = r1.splitmix64_uniform(idx, r1.ROLE_SEED)

        tr = is_source & (role < 0.30)
        se = is_source & (role >= 0.30) & (role < 0.50)

        if np.any(tr):
            Xtr.append(X[tr].copy())
            itr.append(idx[tr].copy())

        if np.any(se):
            Xse.append(X[se].copy())
            ase.append(df["treatment"].to_numpy(np.float32, copy=False)[se].copy())
            yse.append(df["visit"].to_numpy(np.float32, copy=False)[se].copy())
            ise.append(idx[se].copy())

        total += n
        print(f"  [{shift_row['label']}] chunk={ci+1} rows={total:,}")

    return (
        np.vstack(Xtr), np.concatenate(itr),
        np.vstack(Xse), np.concatenate(ase), np.concatenate(yse), np.concatenate(ise),
    )


def fit_topq_in_memory(r1, scores: np.ndarray, row_idx: np.ndarray, q: float):
    scores = np.asarray(scores, dtype=np.float64)
    row_idx = np.asarray(row_idx, dtype=np.uint64)
    n = len(scores)
    k = int(round(q*n))
    c = float(np.partition(scores, n-k)[n-k])

    gt = scores > c
    eq = scores == c
    n_gt = int(gt.sum())
    n_eq = int(eq.sum())
    need = int(k-n_gt)
    if need < 0 or need > n_eq:
        raise RuntimeError("Invalid top-q tie geometry")

    u = r1.splitmix64_uniform(row_idx, TIE_SEED)
    if need == 0:
        u_cut = -1.0
    elif need == n_eq:
        u_cut = 1.0
    else:
        ue = u[eq]
        u_cut = float(np.partition(ue, need-1)[need-1])

    pol = gt | (eq & (u <= u_cut))
    if int(pol.sum()) != k:
        raise RuntimeError(f"Train exact-q failure: wanted {k}, got {pol.sum()}")

    return {
        "score_cut": c,
        "score_cut_hex": c.hex(),
        "tie_u_cut": u_cut,
        "tie_u_cut_hex": float(u_cut).hex(),
        "threshold_tie_count": n_eq,
        "tie_selected_count": need,
        "train_policy_rate": float(pol.mean()),
    }


def apply_rule_in_memory(r1, scores: np.ndarray, row_idx: np.ndarray, rule):
    scores = np.asarray(scores, dtype=np.float64)
    u = r1.splitmix64_uniform(np.asarray(row_idx, dtype=np.uint64), TIE_SEED)
    return (scores > rule["score_cut"]) | (
        (scores == rule["score_cut"]) & (u <= rule["tie_u_cut"])
    )


def ipw_gain(policy, a, y, ehat):
    p = policy.astype(np.float64)
    a = a.astype(np.float64)
    y = y.astype(np.float64)
    e = np.asarray(ehat, dtype=np.float64)
    psi = p * (a/e*y - (1-a)/(1-e)*y)
    return float(psi.mean()), float(psi.std(ddof=1)/math.sqrt(len(psi)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--r0-outdir", required=True)
    ap.add_argument("--r01-outdir", required=True)
    ap.add_argument("--r1-source", required=True)
    ap.add_argument("--r12-source", required=True)
    ap.add_argument("--r1-outdir", required=True)
    ap.add_argument("--r12-outdir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--chunksize", type=int, default=500_000)
    args = ap.parse_args()

    data = Path(args.data).resolve()
    r0 = Path(args.r0_outdir).resolve()
    r01 = Path(args.r01_outdir).resolve()
    r1out = Path(args.r1_outdir).resolve()
    r12out = Path(args.r12_outdir).resolve()
    out = Path(args.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    print("R1F-1 Verify frozen R1/R1.2 provenance...")
    r1, r1sha = load_module(Path(args.r1_source).resolve(), EXPECTED_R1_SHA256, "r1_frozen")
    _, r12sha = load_module(Path(args.r12_source).resolve(), EXPECTED_R12_SHA256, "r12_frozen")
    frozen = r1.load_frozen_shift(r0, r01)

    prior_r12 = pd.read_csv(r12out/"criteo_r12_propensity_adjusted_source_selection.csv")

    selection_rows, winner_rows, forensic_rows = [], [], []

    for _, shift in frozen["shifts"].iterrows():
        name = str(shift["label"])
        print(f"\nR1F-2 Rebuild frozen source train/select for {name}...")
        Xtr, itr, Xse, ase, yse, ise = collect_source_train_select(
            r1, data, frozen, shift, args.chunksize
        )

        propensity_path = r12out/"propensity_models"/f"{name}_propensity_logit.joblib"
        propensity = joblib.load(propensity_path)
        e = propensity.predict_proba(Xse.astype(np.float64))[:,1]

        scen = []
        for model_name in r1.MODEL_NAMES:
            bundle = joblib.load(r1out/"models"/name/f"{model_name}.joblib")
            score_tr = r1.predict_tau(bundle, Xtr.astype(np.float64, copy=False))
            score_se = r1.predict_tau(bundle, Xse.astype(np.float64, copy=False))

            for q in BUDGETS:
                # Critical correction: rule is constructed and applied in the SAME
                # process, before any decimal serialization.
                rule = fit_topq_in_memory(r1, score_tr, itr, q)
                pol = apply_rule_in_memory(r1, score_se, ise, rule)
                rate = float(pol.mean())
                gain, se = ipw_gain(pol, ase, yse, e)

                old = prior_r12[
                    (prior_r12.scenario==name)&
                    (prior_r12.model==model_name)&
                    (np.isclose(prior_r12.budget,q))
                ].iloc[0]

                row = {
                    "scenario":name,
                    "budget":q,
                    "model":model_name,
                    "score_cut_hex":rule["score_cut_hex"],
                    "tie_u_cut_hex":rule["tie_u_cut_hex"],
                    "score_cut_decimal":rule["score_cut"],
                    "tie_u_cut_decimal":rule["tie_u_cut"],
                    "threshold_tie_count_train":rule["threshold_tie_count"],
                    "tie_selected_count_train":rule["tie_selected_count"],
                    "source_train_policy_rate":rule["train_policy_rate"],
                    "source_select_policy_rate":rate,
                    "source_select_abs_budget_deviation":abs(rate-q),
                    "propensity_adjusted_ipw_gain":gain,
                    "propensity_adjusted_ipw_se":se,
                    "invalid_r12_policy_rate":float(old.source_select_policy_rate),
                    "r1f_minus_invalid_r12_policy_rate":rate-float(old.source_select_policy_rate),
                }
                selection_rows.append(row)
                scen.append(row)

        temp = pd.DataFrame(scen)
        for q in BUDGETS:
            g = temp[np.isclose(temp.budget,q)].sort_values(
                ["propensity_adjusted_ipw_gain","model"], ascending=[False,True]
            )
            b, s = g.iloc[0], g.iloc[1]
            winner_rows.append({
                "scenario":name,
                "budget":q,
                "final_source_winner":b.model,
                "winner_gain":float(b.propensity_adjusted_ipw_gain),
                "runner_up":s.model,
                "runner_up_gain":float(s.propensity_adjusted_ipw_gain),
                "winner_minus_runner_up":float(
                    b.propensity_adjusted_ipw_gain-s.propensity_adjusted_ipw_gain
                ),
            })

        del Xtr, itr, Xse, ase, yse, ise, propensity

    selection = pd.DataFrame(selection_rows)
    winners = pd.DataFrame(winner_rows)
    selection.to_csv(out/"criteo_r1f_source_selection.csv", index=False)
    winners.to_csv(out/"criteo_r1f_source_winners.csv", index=False)

    # Forensic proof of the R1.2 serialization bug.
    bad = selection[np.abs(selection.invalid_r12_policy_rate-selection.budget)>.005]
    forensic = {
        "r12_policies_outside_budget_tolerance": int(len(bad)),
        "r1f_policies_outside_budget_tolerance": int(
            (selection.source_select_abs_budget_deviation>.005).sum()
        ),
        "max_r1f_budget_deviation": float(selection.source_select_abs_budget_deviation.max()),
        "max_invalid_r12_budget_deviation": float(
            np.max(np.abs(selection.invalid_r12_policy_rate-selection.budget))
        ),
        "all_train_rates_exact": bool(
            np.all(np.abs(selection.source_train_policy_rate-selection.budget)<=1e-12)
        ),
        "note": "R1F recomputes and applies top-q cutoffs in-memory; saved hex strings are provenance only.",
    }
    (out/"criteo_r1f_forensic.json").write_text(json.dumps(forensic,indent=2),encoding="utf-8")

    gate = pd.DataFrame([{
        "all_source_train_budgets_exact":forensic["all_train_rates_exact"],
        "all_source_select_budgets_within_005":bool(
            np.all(selection.source_select_abs_budget_deviation<=.005)
        ),
        "all_gains_finite":bool(np.isfinite(selection.propensity_adjusted_ipw_gain).all()),
        "nine_winners_defined":len(winners)==9,
        "frozen_r12_propensity_models_reused":True,
        "candidate_models_retrained":False,
        "target_outcomes_used":False,
        "source_infer_outcomes_used":False,
    }])
    gate.to_csv(out/"criteo_r1f_gate.csv",index=False)

    summary = {
        "stage":"Criteo R1F Technical Finalization",
        "r1_sha256":r1sha,
        "r12_sha256":r12sha,
        "all_technical_finalization_gates_pass":bool(
            gate[[
                "all_source_train_budgets_exact",
                "all_source_select_budgets_within_005",
                "all_gains_finite",
                "nine_winners_defined",
                "frozen_r12_propensity_models_reused",
            ]].all(axis=None)
        ),
        "r12_strict_propensity_gate_status":"FAIL remains permanent",
        "criteo_role":"secondary large-scale real-data application/benchmark, not primary causal validation",
        "next_if_pass":"Freeze R1F source winners. Proceed to R2 with target outcomes still hidden.",
    }
    (out/"criteo_r1f_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

    print("\n=== R1F FINAL SOURCE WINNERS ===")
    print(winners.to_string(index=False))
    print("\n=== R1F FORENSIC ===")
    print(forensic)
    print("\n=== R1F GATE ===")
    print(gate.to_string(index=False))
    print("\nSummary:", summary)
    print("\nFinished. Results:", out)


if __name__ == "__main__":
    main()
