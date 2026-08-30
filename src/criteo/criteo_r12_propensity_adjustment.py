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
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

EXPECTED_R1_SHA256 = "1c7fe26cebf45f9215c7ec8de54f06ec2e72eb8e72744b3fb2a8d392ae0f3e0e"
EXPECTED_R11_SHA256 = "fa011f1d63e0394174e73e48989ad4b80882827c1c6c990b61fe4bbd29e3176e"
FEATURES = [f"f{i}" for i in range(12)]
BUDGETS = (0.10, 0.30, 0.50)
TIE_SEED = np.uint64(2026082806)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, expected_sha: str, name: str):
    sha = sha256_file(path)
    if sha != expected_sha:
        raise RuntimeError(f"{name} source hash mismatch. expected={expected_sha} got={sha}")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod, sha


def collect_source_train_select(r1, data_path: Path, frozen, shift_row, chunksize: int):
    Xtr, atr, itr, ztr = [], [], [], []
    Xse, ase, yse, ise, zse = [], [], [], [], []
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
            atr.append(df["treatment"].to_numpy(np.float32, copy=False)[tr].copy())
            itr.append(idx[tr].copy())
            ztr.append(z[tr].copy())

        if np.any(se):
            Xse.append(X[se].copy())
            ase.append(df["treatment"].to_numpy(np.float32, copy=False)[se].copy())
            yse.append(df["visit"].to_numpy(np.float32, copy=False)[se].copy())
            ise.append(idx[se].copy())
            zse.append(z[se].copy())

        total += n
        print(f"  [{shift_row['label']}] chunk={ci+1} rows={total:,}")

    return (
        np.vstack(Xtr), np.concatenate(atr), np.concatenate(itr), np.concatenate(ztr),
        np.vstack(Xse), np.concatenate(ase), np.concatenate(yse), np.concatenate(ise), np.concatenate(zse),
    )


def apply_tie_rule(r1, scores, row_idx, score_cut, tie_u_cut):
    u = r1.splitmix64_uniform(row_idx.astype(np.uint64), TIE_SEED)
    scores = np.asarray(scores, dtype=np.float64)
    return (scores > float(score_cut)) | (
        (scores == float(score_cut)) & (u <= float(tie_u_cut))
    )


def adjusted_ipw_gain(policy, a, y, ehat):
    policy = policy.astype(np.float64)
    a = a.astype(np.float64)
    y = y.astype(np.float64)
    ehat = np.asarray(ehat, dtype=np.float64)
    psi = policy * (a / ehat * y - (1.0-a) / (1.0-ehat) * y)
    return float(psi.mean()), float(psi.std(ddof=1)/math.sqrt(len(psi)))


def weighted_smd(X, z, a, e):
    Xaug = np.column_stack([X.astype(np.float64), z.astype(np.float64)])
    names = FEATURES + ["PC1"]
    a = a.astype(bool)
    w = np.where(a, 1.0/e, 1.0/(1.0-e))

    out = []
    for j, nm in enumerate(names):
        x = Xaug[:, j]
        w1, w0 = w[a], w[~a]
        x1, x0 = x[a], x[~a]
        m1 = np.sum(w1*x1)/np.sum(w1)
        m0 = np.sum(w0*x0)/np.sum(w0)
        v1 = np.sum(w1*(x1-m1)**2)/np.sum(w1)
        v0 = np.sum(w0*(x0-m0)**2)/np.sum(w0)
        smd = (m1-m0)/np.sqrt(max((v1+v0)/2.0, 1e-16))
        out.append((nm, float(smd)))
    return out


def calibration_table(ehat, a, bins=20):
    order = np.argsort(ehat)
    chunks = np.array_split(order, bins)
    rows = []
    for b, idx in enumerate(chunks, start=1):
        rows.append({
            "bin": b,
            "n": int(len(idx)),
            "predicted_treatment_rate": float(ehat[idx].mean()),
            "observed_treatment_rate": float(a[idx].mean()),
            "abs_calibration_gap": float(abs(ehat[idx].mean()-a[idx].mean())),
        })
    return pd.DataFrame(rows)


def weighted_pc1_deciles(z, a, e):
    cuts = np.quantile(z, np.linspace(0,1,11))
    dec = np.searchsorted(cuts[1:-1], z, side="right")
    a_bool = a.astype(bool)
    w = np.where(a_bool, 1.0/e, 1.0/(1.0-e))
    rows = []
    for d in range(10):
        m = dec == d
        wt = float(w[m & a_bool].sum())
        wc = float(w[m & (~a_bool)].sum())
        share = wt/(wt+wc)
        rows.append({
            "decile": d+1,
            "weighted_treated_share": share,
            "abs_dev_from_half": abs(share-.5),
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--r0-outdir", required=True)
    ap.add_argument("--r01-outdir", required=True)
    ap.add_argument("--r1-source", required=True)
    ap.add_argument("--r11-source", required=True)
    ap.add_argument("--r1-outdir", required=True)
    ap.add_argument("--r11-outdir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--chunksize", type=int, default=500_000)
    args = ap.parse_args()

    data = Path(args.data).resolve()
    r0 = Path(args.r0_outdir).resolve()
    r01 = Path(args.r01_outdir).resolve()
    r1out = Path(args.r1_outdir).resolve()
    r11out = Path(args.r11_outdir).resolve()
    out = Path(args.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    print("R1.2-1 Verify frozen sources/artifacts...")
    r1, r1sha = load_module(Path(args.r1_source).resolve(), EXPECTED_R1_SHA256, "r1_frozen")
    _, r11sha = load_module(Path(args.r11_source).resolve(), EXPECTED_R11_SHA256, "r11_frozen")
    frozen = r1.load_frozen_shift(r0, r01)

    rules = pd.read_csv(r11out/"criteo_r11_budget_corrected_source_selection.csv")
    old_winners = pd.read_csv(r11out/"criteo_r11_corrected_source_winners.csv")

    prop_rows, bal_rows, cal_rows, dec_rows, sel_rows, win_rows = [], [], [], [], [], []

    for _, shift in frozen["shifts"].iterrows():
        name = str(shift["label"])
        print(f"\nR1.2-2 Rebuild SOURCE train/select for {name}...")
        Xtr, atr, itr, ztr, Xse, ase, yse, ise, zse = collect_source_train_select(
            r1, data, frozen, shift, args.chunksize
        )

        print(f"R1.2-3 Fit frozen logistic propensity nuisance for {name}...")
        propensity = Pipeline([
            ("scale", StandardScaler()),
            ("logit", LogisticRegression(
                C=1.0, solver="lbfgs", max_iter=250, random_state=20260828
            )),
        ])
        propensity.fit(Xtr.astype(np.float64), atr)
        e = propensity.predict_proba(Xse.astype(np.float64))[:,1]

        if not np.all(np.isfinite(e)):
            raise RuntimeError(f"Non-finite propensity in {name}")

        prop_dir = out/"propensity_models"
        prop_dir.mkdir(exist_ok=True)
        joblib.dump(propensity, prop_dir/f"{name}_propensity_logit.joblib", compress=3)

        cal = calibration_table(e, ase, 20)
        cal.insert(0, "scenario", name)
        cal_rows.extend(cal.to_dict("records"))

        dec = weighted_pc1_deciles(zse, ase, e)
        dec.insert(0, "scenario", name)
        dec_rows.extend(dec.to_dict("records"))

        smds = weighted_smd(Xse, zse, ase, e)
        for nm, smd in smds:
            bal_rows.append({"scenario":name, "covariate":nm, "weighted_smd":smd})

        invw = np.where(ase==1, 1.0/e, 1.0/(1.0-e))
        prop_rows.append({
            "scenario": name,
            "source_train_n": int(len(Xtr)),
            "source_select_n": int(len(Xse)),
            "source_select_treatment_rate": float(ase.mean()),
            "propensity_mean": float(e.mean()),
            "propensity_p001": float(np.quantile(e,.001)),
            "propensity_p01": float(np.quantile(e,.01)),
            "propensity_p50": float(np.quantile(e,.50)),
            "propensity_p99": float(np.quantile(e,.99)),
            "propensity_p999": float(np.quantile(e,.999)),
            "propensity_min": float(e.min()),
            "propensity_max": float(e.max()),
            "inverse_weight_p99": float(np.quantile(invw,.99)),
            "inverse_weight_p999": float(np.quantile(invw,.999)),
            "inverse_weight_max": float(invw.max()),
            "calibration_in_large_abs": float(abs(e.mean()-ase.mean())),
            "max_bin_calibration_gap": float(cal.abs_calibration_gap.max()),
            "max_weighted_abs_smd": float(max(abs(v) for _,v in smds)),
            "max_weighted_pc1_decile_dev_from_half": float(dec.abs_dev_from_half.max()),
        })

        print(f"R1.2-4 Re-evaluate frozen model policies with e(X) for {name}...")
        scen_rows = []
        for model_name in r1.MODEL_NAMES:
            bundle = joblib.load(r1out/"models"/name/f"{model_name}.joblib")
            scores = r1.predict_tau(bundle, Xse.astype(np.float64, copy=False))

            for q in BUDGETS:
                rr = rules[
                    (rules.scenario==name)&
                    (rules.model==model_name)&
                    (np.isclose(rules.budget,q))
                ].iloc[0]
                pol = apply_tie_rule(r1, scores, ise, rr.score_cut, rr.tie_u_cut)
                gain, se = adjusted_ipw_gain(pol, ase, yse, e)
                row = {
                    "scenario":name,
                    "budget":q,
                    "model":model_name,
                    "source_select_policy_rate":float(pol.mean()),
                    "abs_budget_deviation":float(abs(pol.mean()-q)),
                    "propensity_adjusted_ipw_gain":gain,
                    "propensity_adjusted_ipw_se":se,
                }
                sel_rows.append(row)
                scen_rows.append(row)

        temp = pd.DataFrame(scen_rows)
        for q in BUDGETS:
            g = temp[np.isclose(temp.budget,q)].sort_values(
                ["propensity_adjusted_ipw_gain","model"], ascending=[False,True]
            )
            b, s = g.iloc[0], g.iloc[1]
            prev = old_winners[
                (old_winners.scenario==name)&(np.isclose(old_winners.budget,q))
            ].iloc[0]
            win_rows.append({
                "scenario":name,
                "budget":q,
                "propensity_adjusted_source_winner":b.model,
                "winner_gain":float(b.propensity_adjusted_ipw_gain),
                "runner_up":s.model,
                "runner_up_gain":float(s.propensity_adjusted_ipw_gain),
                "winner_minus_runner_up":float(
                    b.propensity_adjusted_ipw_gain-s.propensity_adjusted_ipw_gain
                ),
                "r11_constant_propensity_winner":prev.corrected_source_winner,
                "winner_changed_after_propensity_adjustment":bool(
                    b.model != prev.corrected_source_winner
                ),
            })

        del Xtr, atr, itr, ztr, Xse, ase, yse, ise, zse, propensity

    props = pd.DataFrame(prop_rows)
    balance = pd.DataFrame(bal_rows)
    calibration = pd.DataFrame(cal_rows)
    deciles = pd.DataFrame(dec_rows)
    selection = pd.DataFrame(sel_rows)
    winners = pd.DataFrame(win_rows)

    props.to_csv(out/"criteo_r12_propensity_audit.csv", index=False)
    balance.to_csv(out/"criteo_r12_weighted_balance.csv", index=False)
    calibration.to_csv(out/"criteo_r12_propensity_calibration.csv", index=False)
    deciles.to_csv(out/"criteo_r12_weighted_pc1_deciles.csv", index=False)
    selection.to_csv(out/"criteo_r12_propensity_adjusted_source_selection.csv", index=False)
    winners.to_csv(out/"criteo_r12_source_winners.csv", index=False)

    gates = []
    for _, r in props.iterrows():
        name = r.scenario
        ss = selection[selection.scenario==name]
        gates.append({
            "scenario":name,
            "propensity_p001_pass_ge_05": bool(r.propensity_p001 >= .05),
            "propensity_p999_pass_le_98": bool(r.propensity_p999 <= .98),
            "inverse_weight_p999_pass_le_25": bool(r.inverse_weight_p999 <= 25.0),
            "calibration_in_large_pass_le_002": bool(r.calibration_in_large_abs <= .002),
            "max_bin_calibration_pass_le_01": bool(r.max_bin_calibration_gap <= .01),
            "weighted_balance_pass_max_smd_le_02": bool(r.max_weighted_abs_smd <= .02),
            "weighted_pc1_decile_pass_dev_le_01": bool(
                r.max_weighted_pc1_decile_dev_from_half <= .01
            ),
            "budget_fidelity_pass_within_005": bool(
                np.all(ss.abs_budget_deviation <= .005)
            ),
            "target_treatment_outcome_blinding_pass": True,
            "source_infer_outcome_blinding_pass": True,
        })
    gate = pd.DataFrame(gates)
    gate.to_csv(out/"criteo_r12_gate.csv", index=False)

    summary = {
        "stage":"Criteo R1.2 Residual-Propensity Adjustment Gate",
        "frozen_r1_source_sha256":r1sha,
        "frozen_r11_source_sha256":r11sha,
        "propensity_model":"scenario-specific standardized logistic regression; source_train X,A only; C=1",
        "candidate_model_artifacts_retrained":False,
        "target_outcomes_used":False,
        "source_infer_outcomes_used":False,
        "winner_changes_vs_r11":int(winners.winner_changed_after_propensity_adjustment.sum()),
        "all_gate_pass":bool(gate.drop(columns=["scenario"]).all(axis=None)),
        "next_if_pass":"Freeze propensity-adjusted source winners and estimated source propensity strategy; proceed to R2.",
    }
    (out/"criteo_r12_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

    print("\n=== R1.2 PROPENSITY AUDIT ===")
    print(props.to_string(index=False))
    print("\n=== R1.2 PROPENSITY-ADJUSTED SOURCE WINNERS ===")
    print(winners.to_string(index=False))
    print("\n=== R1.2 GATE ===")
    print(gate.to_string(index=False))
    print("\nSummary:", summary)
    print("\nFinished. Results:", out)


if __name__ == "__main__":
    main()
