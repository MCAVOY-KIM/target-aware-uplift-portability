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
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

EXPECTED_R1_SHA256 = "1c7fe26cebf45f9215c7ec8de54f06ec2e72eb8e72744b3fb2a8d392ae0f3e0e"
EXPECTED_R2_PAIR_SHA256 = "5949d500efbc74a0fe033f81eb47ed6374f158c378b64d453ffa240c398b7a23"
EXPECTED_R2_BOUND_SHA256 = "674ffed3be874de1fb6c76f376d6d726288dc9eaefdeb4e99d656888dcd3cbba"
EXPECTED_R2_RULE_SHA256 = "fcd9a4fd92540119948868ffe840121d5b44362700e9213a7839b4178d10e224"
EXPECTED_R2_RATIO_SHA256 = "2b01c556a943ce9fecdde1a7543b60c1aa78840f61fd6196cb04b0587e38138a"
EXPECTED_R2_SUMMARY_SHA256 = "52bae0852cea4f69de511cba45c9c10316f08712b98095f72f2c33bd2d08efa7"

FEATURES = [f"f{i}" for i in range(12)]
MODELS = ("S-Logit","T-Logit","S-HGB","T-HGB","TO-HGB","DR-HGB")
BUDGETS = (0.10,0.30,0.50)
EPSILON_GRID = (0.0005,0.0010,0.0020,0.0050)
TIE_SEED = np.uint64(2026082806)
GAUSSIAN_DRAWS = 20_000
GAUSSIAN_SEED_BASE = 2026082811


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_hash(path: Path, expected: str, label: str):
    got=sha256_file(path)
    if got != expected:
        raise RuntimeError(f"{label} hash mismatch: expected={expected} got={got}")
    return got


def load_r1_module(path: Path):
    sha=sha256_file(path)
    if sha != EXPECTED_R1_SHA256:
        raise RuntimeError(f"R1 source hash mismatch: {sha}")
    spec=importlib.util.spec_from_file_location("r1_frozen",path)
    mod=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod,sha


def r2_rule_lookup(rule_df):
    out={}
    for _,r in rule_df.iterrows():
        out[(r.scenario,r.model,float(r.budget))]={
            "score_cut":float.fromhex(r.score_cut_hex),
            "tie_u_cut":float.fromhex(r.tie_u_cut_hex),
            "r2_target_infer_rate":float(r.target_infer_rate),
        }
    return out


def apply_rule(r1,score,row_idx,rule):
    score=np.asarray(score,dtype=np.float64)
    u=r1.splitmix64_uniform(np.asarray(row_idx,dtype=np.uint64),TIE_SEED)
    return (score > rule["score_cut"]) | (
        (score == rule["score_cut"]) & (u <= rule["tie_u_cut"])
    )


class Moments:
    def __init__(self,k):
        self.k=k
        self.n=0
        self.sum=np.zeros(k,dtype=np.float64)
        self.cross=np.zeros((k,k),dtype=np.float64)

    def update(self,Z):
        Z=np.asarray(Z,dtype=np.float64)
        if len(Z)==0:
            return
        self.n += len(Z)
        self.sum += Z.sum(axis=0)
        self.cross += Z.T@Z

    def mean(self):
        return self.sum/self.n

    def covariance_of_mean(self):
        if self.n <= 1:
            raise RuntimeError("Insufficient target-infer rows")
        centered=self.cross-np.outer(self.sum,self.sum)/self.n
        sample_cov=centered/(self.n-1)
        return sample_cov/self.n


def stabilize_corr(cov):
    se=np.sqrt(np.maximum(np.diag(cov),0))
    if np.any(se<=1e-12):
        raise RuntimeError("Degenerate benchmark contrast SE")
    corr=cov/np.outer(se,se)
    corr=(corr+corr.T)/2
    np.fill_diagonal(corr,1.0)
    vals,vecs=np.linalg.eigh(corr)
    min_eig=float(vals.min())
    vals=np.maximum(vals,1e-10)
    c=(vecs*vals)@vecs.T
    d=np.sqrt(np.diag(c))
    c=c/np.outer(d,d)
    return se,c,min_eig


def gaussian_critical(corr,seed):
    rng=np.random.default_rng(seed)
    z=rng.multivariate_normal(
        np.zeros(corr.shape[0]),corr,size=GAUSSIAN_DRAWS,
        check_valid="ignore",method="svd"
    )
    return float(np.quantile(z.max(axis=1),.95))


def collect_target_adapt(r1,data,frozen,shift,chunksize):
    Xs,As,Ys=[],[],[]
    total=0
    usecols=FEATURES+["treatment","visit"]
    for ci,df in enumerate(pd.read_csv(data,compression="gzip",usecols=usecols,chunksize=chunksize)):
        n=len(df)
        idx=np.arange(total,total+n,dtype=np.uint64)
        X=df[FEATURES].to_numpy(np.float32,copy=False)
        z=r1.pc1_z(X.astype(np.float64,copy=False),frozen)
        pt=r1.p_target_from_z(z,shift)
        target=r1.splitmix64_uniform(idx,r1.MEMBERSHIP_SEED)<pt
        role=r1.splitmix64_uniform(idx,r1.ROLE_SEED)
        adapt=target & (role<.25)

        if np.any(adapt):
            Xs.append(X[adapt].copy())
            As.append(df["treatment"].to_numpy(np.float32,copy=False)[adapt].copy())
            Ys.append(df["visit"].to_numpy(np.float32,copy=False)[adapt].copy())

        total += n
        print(f"  [unlock-adapt {shift['label']}] chunk={ci+1} rows={total:,}")
    return np.vstack(Xs),np.concatenate(As),np.concatenate(Ys)


def fit_target_nuisances(X,a,y,scenario_index):
    prop=Pipeline([
        ("scale",StandardScaler()),
        ("logit",LogisticRegression(
            C=1.0,solver="lbfgs",max_iter=250,random_state=20260829+scenario_index
        )),
    ])
    prop.fit(X.astype(np.float64),a)

    base_params=dict(
        learning_rate=0.05,
        max_iter=150,
        max_leaf_nodes=31,
        min_samples_leaf=200,
        l2_regularization=1.0,
        max_bins=255,
        early_stopping=True,
        validation_fraction=0.10,
        n_iter_no_change=15,
    )
    p0=dict(base_params); p0["random_state"]=20260840+scenario_index*2
    p1=dict(base_params); p1["random_state"]=20260841+scenario_index*2
    m0=HistGradientBoostingClassifier(**p0)
    m1=HistGradientBoostingClassifier(**p1)
    m0.fit(X[a==0].astype(np.float64),y[a==0])
    m1.fit(X[a==1].astype(np.float64),y[a==1])
    return prop,m0,m1


def calibration_table(e,a,bins=20):
    order=np.argsort(e)
    chunks=np.array_split(order,bins)
    rows=[]
    for b,ii in enumerate(chunks,start=1):
        rows.append({
            "bin":b,
            "n":int(len(ii)),
            "predicted_rate":float(e[ii].mean()),
            "observed_rate":float(a[ii].mean()),
            "abs_gap":float(abs(e[ii].mean()-a[ii].mean())),
        })
    return pd.DataFrame(rows)


def weighted_balance_from_acc(acc):
    rows=[]
    for name,j in zip(FEATURES+["PC1"],range(13)):
        wt=acc["wt_t"]; wc=acc["wt_c"]
        mt=acc["sum_t"][j]/wt; mc=acc["sum_c"][j]/wc
        vt=acc["sq_t"][j]/wt-mt*mt
        vc=acc["sq_c"][j]/wc-mc*mc
        smd=(mt-mc)/math.sqrt(max((vt+vc)/2,1e-16))
        rows.append((name,float(smd)))
    return rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",required=True)
    ap.add_argument("--r0-outdir",required=True)
    ap.add_argument("--r01-outdir",required=True)
    ap.add_argument("--r1-source",required=True)
    ap.add_argument("--r1-outdir",required=True)
    ap.add_argument("--r2-outdir",required=True)
    ap.add_argument("--outdir",required=True)
    ap.add_argument("--chunksize",type=int,default=500_000)
    args=ap.parse_args()

    data=Path(args.data).resolve()
    r0=Path(args.r0_outdir).resolve()
    r01=Path(args.r01_outdir).resolve()
    r1out=Path(args.r1_outdir).resolve()
    r2out=Path(args.r2_outdir).resolve()
    out=Path(args.outdir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    (out/"target_benchmark_nuisance").mkdir(exist_ok=True)

    print("R3-1 Verify frozen R2 artifacts BEFORE outcome benchmark...")
    r1,r1sha=load_r1_module(Path(args.r1_source).resolve())
    verify_hash(r2out/"criteo_r2_pairwise_contrasts.csv",EXPECTED_R2_PAIR_SHA256,"R2 pairwise")
    verify_hash(r2out/"criteo_r2_portability_bounds.csv",EXPECTED_R2_BOUND_SHA256,"R2 bounds")
    verify_hash(r2out/"criteo_r2_target_policy_rules.csv",EXPECTED_R2_RULE_SHA256,"R2 rules")
    verify_hash(r2out/"criteo_r2_ratio_inference_audit.csv",EXPECTED_R2_RATIO_SHA256,"R2 ratio audit")
    verify_hash(r2out/"criteo_r2_summary.json",EXPECTED_R2_SUMMARY_SHA256,"R2 summary")

    r2pair=pd.read_csv(r2out/"criteo_r2_pairwise_contrasts.csv")
    r2bounds=pd.read_csv(r2out/"criteo_r2_portability_bounds.csv")
    r2rules=pd.read_csv(r2out/"criteo_r2_target_policy_rules.csv")
    rules=r2_rule_lookup(r2rules)
    frozen=r1.load_frozen_shift(r0,r01)

    gain_rows=[]
    pair_rows=[]
    regret_rows=[]
    compare_rows=[]
    tol_rows=[]
    prop_rows=[]
    calib_rows=[]
    balance_rows=[]
    gate_rows=[]

    for sidx,(_,shift) in enumerate(frozen["shifts"].iterrows()):
        name=str(shift["label"])
        print(f"\\nR3-2 FIRST OUTCOME UNLOCK: collect target_adapt A/Y for {name}...")
        Xa,aa,ya=collect_target_adapt(r1,data,frozen,shift,args.chunksize)

        print(f"R3-3 Fit fixed TARGET benchmark nuisances for {name}...")
        prop,m0,m1=fit_target_nuisances(Xa,aa,ya,sidx)
        joblib.dump(prop,out/"target_benchmark_nuisance"/f"{name}_propensity.joblib",compress=3)
        joblib.dump(m0,out/"target_benchmark_nuisance"/f"{name}_outcome_control.joblib",compress=3)
        joblib.dump(m1,out/"target_benchmark_nuisance"/f"{name}_outcome_treated.joblib",compress=3)

        bundles={
            m:joblib.load(r1out/"models"/name/f"{m}.joblib")
            for m in MODELS
        }

        # Frozen directed contrast order comes directly from R2.
        cdf=r2pair[r2pair.scenario==name].reset_index(drop=True)
        if len(cdf)!=15:
            raise RuntimeError("Expected 15 frozen R2 contrasts")

        gain_keys=[(m,q) for q in BUDGETS for m in MODELS]
        gain_index={k:i for i,k in enumerate(gain_keys)}
        gm=Moments(len(gain_keys))
        cm=Moments(15)
        ipw_sum=np.zeros(15,dtype=np.float64)
        ninf=0
        policy_counts={k:0 for k in gain_keys}

        e_parts=[]; a_parts=[]
        bal={
            "wt_t":0.0,"wt_c":0.0,
            "sum_t":np.zeros(13),"sum_c":np.zeros(13),
            "sq_t":np.zeros(13),"sq_c":np.zeros(13),
        }

        events=treated=0
        total=0
        print(f"R3-4 Stream target_infer A/Y benchmark for {name}...")
        usecols=FEATURES+["treatment","visit"]
        for ci,df in enumerate(pd.read_csv(data,compression="gzip",usecols=usecols,chunksize=args.chunksize)):
            n=len(df)
            idx=np.arange(total,total+n,dtype=np.uint64)
            X=df[FEATURES].to_numpy(np.float32,copy=False)
            z=r1.pc1_z(X.astype(np.float64,copy=False),frozen)
            pt=r1.p_target_from_z(z,shift)
            target=r1.splitmix64_uniform(idx,r1.MEMBERSHIP_SEED)<pt
            role=r1.splitmix64_uniform(idx,r1.ROLE_SEED)
            inf=target & (role>=.25)

            if np.any(inf):
                Xi=X[inf].astype(np.float64,copy=False)
                zi=z[inf].astype(np.float64)
                Ii=idx[inf]
                ai=df["treatment"].to_numpy(np.float32,copy=False)[inf].astype(np.float64)
                yi=df["visit"].to_numpy(np.float32,copy=False)[inf].astype(np.float64)
                ni=len(Xi)
                ninf += ni
                events += int(yi.sum())
                treated += int(ai.sum())

                e=np.clip(prop.predict_proba(Xi)[:,1],.02,.98)
                mu0=m0.predict_proba(Xi)[:,1]
                mu1=m1.predict_proba(Xi)[:,1]
                aipw_tau=(
                    (mu1-mu0)
                    +ai/e*(yi-mu1)
                    -(1-ai)/(1-e)*(yi-mu0)
                )
                ipw_tau=ai/e*yi-(1-ai)/(1-e)*yi

                e_parts.append(e.astype(np.float32))
                a_parts.append(ai.astype(np.uint8))

                Xaug=np.column_stack([Xi,zi])
                at=ai==1
                ac=~at
                wt=1/e[at]
                wc=1/(1-e[ac])
                bal["wt_t"] += float(wt.sum())
                bal["wt_c"] += float(wc.sum())
                bal["sum_t"] += (Xaug[at]*wt[:,None]).sum(axis=0)
                bal["sum_c"] += (Xaug[ac]*wc[:,None]).sum(axis=0)
                bal["sq_t"] += ((Xaug[at]**2)*wt[:,None]).sum(axis=0)
                bal["sq_c"] += ((Xaug[ac]**2)*wc[:,None]).sum(axis=0)

                pol={}
                for m in MODELS:
                    score=r1.predict_tau(bundles[m],Xi)
                    for q in BUDGETS:
                        rr=rules[(name,m,q)]
                        pp=apply_rule(r1,score,Ii,rr)
                        pol[(m,q)]=pp
                        policy_counts[(m,q)] += int(pp.sum())

                G=np.empty((ni,len(gain_keys)),dtype=np.float64)
                for k,(m,q) in enumerate(gain_keys):
                    G[:,k]=pol[(m,q)].astype(np.float64)*aipw_tau
                gm.update(G)

                C=np.empty((ni,15),dtype=np.float64)
                CIPW=np.empty((ni,15),dtype=np.float64)
                for k,r in cdf.iterrows():
                    q=float(r.budget)
                    h=(
                        pol[(r.competitor,q)].astype(np.float64)
                        -pol[(r.source_winner,q)].astype(np.float64)
                    )
                    C[:,k]=h*aipw_tau
                    CIPW[:,k]=h*ipw_tau
                cm.update(C)
                ipw_sum += CIPW.sum(axis=0)

            total += n
            print(f"  [benchmark {name}] chunk={ci+1} rows={total:,}")

        gains=gm.mean()
        delta=cm.mean()
        cov=cm.covariance_of_mean()
        se,corr,min_eig=stabilize_corr(cov)
        crit=gaussian_critical(corr,GAUSSIAN_SEED_BASE+sidx)
        lo=delta-crit*se
        up=delta+crit*se
        ipw_delta=ipw_sum/ninf

        # Propensity benchmark diagnostics on independent target_infer.
        ev=np.concatenate(e_parts).astype(np.float64)
        av=np.concatenate(a_parts).astype(np.float64)
        cal=calibration_table(ev,av,20)
        cal.insert(0,"scenario",name)
        calib_rows.extend(cal.to_dict("records"))
        wb=weighted_balance_from_acc(bal)
        for nm,smd in wb:
            balance_rows.append({"scenario":name,"covariate":nm,"weighted_smd":smd})

        prop_rows.append({
            "scenario":name,
            "target_adapt_n":int(len(Xa)),
            "target_adapt_treatment_rate":float(aa.mean()),
            "target_adapt_visit_rate":float(ya.mean()),
            "target_adapt_control_events":int(ya[aa==0].sum()),
            "target_adapt_treated_events":int(ya[aa==1].sum()),
            "target_infer_n":int(ninf),
            "target_infer_treatment_rate":treated/ninf,
            "target_infer_visit_rate":events/ninf,
            "propensity_mean":float(ev.mean()),
            "propensity_p001":float(np.quantile(ev,.001)),
            "propensity_p999":float(np.quantile(ev,.999)),
            "calibration_in_large_abs":float(abs(ev.mean()-av.mean())),
            "max_20bin_calibration_gap":float(cal.abs_gap.max()),
            "max_weighted_abs_smd":float(max(abs(v) for _,v in wb)),
            "benchmark_corr_min_eigenvalue":min_eig,
            "benchmark_gaussian_critical":crit,
        })

        # Policy gain table.
        for k,(m,q) in enumerate(gain_keys):
            gain_rows.append({
                "scenario":name,"budget":q,"model":m,
                "target_aipw_gain":float(gains[k]),
                "target_infer_policy_rate":policy_counts[(m,q)]/ninf,
                "r2_frozen_target_infer_policy_rate":rules[(name,m,q)]["r2_target_infer_rate"],
                "policy_rate_reproduction_abs_diff":abs(
                    policy_counts[(m,q)]/ninf
                    -rules[(name,m,q)]["r2_target_infer_rate"]
                ),
            })

        # Pairwise table and exact R2 comparison.
        for k,r in cdf.iterrows():
            pair_rows.append({
                "scenario":name,
                "budget":float(r.budget),
                "source_winner":r.source_winner,
                "competitor":r.competitor,
                "target_aipw_delta":float(delta[k]),
                "target_aipw_se":float(se[k]),
                "target_aipw_lower_95_family":float(lo[k]),
                "target_aipw_upper_95_family":float(up[k]),
                "target_ipw_delta_sensitivity":float(ipw_delta[k]),
                "target_aipw_minus_ipw":float(delta[k]-ipw_delta[k]),
                "r2_transported_delta":float(r.delta_hat),
                "r2_transported_se":float(r.se_hat),
                "r2_upper_95_family":float(r.upper_95_one_sided_family),
                "r2_minus_target_benchmark_delta":float(r.delta_hat-delta[k]),
            })

        # Regret summaries.
        pairtemp=pd.DataFrame([r for r in pair_rows if r["scenario"]==name])
        gaintemp=pd.DataFrame([r for r in gain_rows if r["scenario"]==name])
        for q in BUDGETS:
            pg=pairtemp[np.isclose(pairtemp.budget,q)]
            gg=gaintemp[np.isclose(gaintemp.budget,q)].sort_values(
                ["target_aipw_gain","model"],ascending=[False,True]
            )
            source_winner=pg.iloc[0].source_winner
            target_best=gg.iloc[0].model
            regret=max(0.0,float(pg.target_aipw_delta.max()))
            regret_up=max(0.0,float(pg.target_aipw_upper_95_family.max()))
            regret_lo=max(0.0,float(pg.target_aipw_lower_95_family.max()))
            ipw_regret=max(0.0,float(pg.target_ipw_delta_sensitivity.max()))
            r2b=r2bounds[
                (r2bounds.scenario==name)&(np.isclose(r2bounds.budget,q))
            ].iloc[0]

            regret_rows.append({
                "scenario":name,"budget":q,
                "source_winner":source_winner,
                "target_best_model_aipw":target_best,
                "source_winner_equals_target_best":bool(source_winner==target_best),
                "target_benchmark_point_regret":regret,
                "target_benchmark_lower_regret_95":regret_lo,
                "target_benchmark_upper_regret_95":regret_up,
                "target_ipw_regret_sensitivity":ipw_regret,
                "r2_point_regret_hat":float(r2b.point_target_regret_hat),
                "r2_asymptotic_upper_regret_bound_95":float(r2b.asymptotic_upper_regret_bound_95),
                "r2_bound_minus_target_benchmark_point_regret":float(
                    r2b.asymptotic_upper_regret_bound_95-regret
                ),
                "benchmark_point_below_r2_bound":bool(
                    regret <= r2b.asymptotic_upper_regret_bound_95
                ),
            })

            for eps in EPSILON_GRID:
                r2_status=(
                    "PORTABLE_AT_TOLERANCE"
                    if float(r2b.asymptotic_upper_regret_bound_95)<=eps
                    else (
                        "EVIDENCE_OF_NON_PORTABILITY"
                        if float(r2b.directional_lower_regret_bound_95)>eps
                        else "UNCERTAIN"
                    )
                )
                benchmark_status=(
                    "BENCHMARK_REGRET_LE_TOLERANCE"
                    if regret<=eps else "BENCHMARK_REGRET_GT_TOLERANCE"
                )
                tol_rows.append({
                    "scenario":name,"budget":q,"epsilon":eps,
                    "r2_status":r2_status,
                    "target_benchmark_status":benchmark_status,
                    "target_benchmark_point_regret":regret,
                    "r2_upper_bound":float(r2b.asymptotic_upper_regret_bound_95),
                    "descriptive_portable_contradiction":bool(
                        r2_status=="PORTABLE_AT_TOLERANCE" and regret>eps
                    ),
                })

        # Technical benchmark gate only. It does NOT gate on R2 agreeing with R3.
        scen_gain=pd.DataFrame([r for r in gain_rows if r["scenario"]==name])
        pa=prop_rows[-1]
        gate_rows.append({
            "scenario":name,
            "r2_policy_rates_reproduced_absdiff_le_1e12":bool(
                np.all(scen_gain.policy_rate_reproduction_abs_diff<=1e-12)
            ),
            "all_target_infer_policy_rates_within_005":bool(
                np.all(np.abs(scen_gain.target_infer_policy_rate-scen_gain.budget)<=.005)
            ),
            "target_propensity_overlap_pass":bool(
                pa["propensity_p001"]>=.05 and pa["propensity_p999"]<=.98
            ),
            "target_propensity_calibration_large_pass_le_002":bool(
                pa["calibration_in_large_abs"]<=.002
            ),
            "target_propensity_max_bin_calibration_pass_le_01":bool(
                pa["max_20bin_calibration_gap"]<=.01
            ),
            "target_weighted_balance_pass_max_smd_le_02":bool(
                pa["max_weighted_abs_smd"]<=.02
            ),
            "target_outcome_nuisance_event_support_pass":bool(
                pa["target_adapt_control_events"]>=1000
                and pa["target_adapt_treated_events"]>=1000
            ),
            "all_benchmark_contrasts_finite":bool(
                np.all(np.isfinite(delta)) and np.all(np.isfinite(se))
            ),
            "benchmark_corr_psd_numeric_pass":bool(min_eig>=-1e-8),
            "target_outcomes_unlocked":True,
        })

        del Xa,aa,ya,prop,m0,m1,bundles

    gains=pd.DataFrame(gain_rows)
    pairs=pd.DataFrame(pair_rows)
    regrets=pd.DataFrame(regret_rows)
    tolerances=pd.DataFrame(tol_rows)
    props=pd.DataFrame(prop_rows)
    calibs=pd.DataFrame(calib_rows)
    balances=pd.DataFrame(balance_rows)
    gates=pd.DataFrame(gate_rows)

    gains.to_csv(out/"criteo_r3_target_benchmark_gains.csv",index=False)
    pairs.to_csv(out/"criteo_r3_target_pairwise_benchmark.csv",index=False)
    regrets.to_csv(out/"criteo_r3_regret_benchmark.csv",index=False)
    tolerances.to_csv(out/"criteo_r3_tolerance_benchmark.csv",index=False)
    props.to_csv(out/"criteo_r3_target_nuisance_audit.csv",index=False)
    calibs.to_csv(out/"criteo_r3_target_propensity_calibration.csv",index=False)
    balances.to_csv(out/"criteo_r3_target_weighted_balance.csv",index=False)
    gates.to_csv(out/"criteo_r3_gate.csv",index=False)

    # Aggregate R2-vs-R3 comparison metrics are descriptive, not tuning gates.
    diff=pairs.r2_transported_delta-pairs.target_aipw_delta
    comparison={
        "n_pairwise_contrasts":int(len(pairs)),
        "pairwise_mae":float(np.mean(np.abs(diff))),
        "pairwise_rmse":float(np.sqrt(np.mean(diff**2))),
        "pairwise_correlation":float(np.corrcoef(
            pairs.r2_transported_delta,pairs.target_aipw_delta
        )[0,1]),
        "pairwise_sign_agreement":float(np.mean(
            np.sign(pairs.r2_transported_delta)==np.sign(pairs.target_aipw_delta)
        )),
        "n_budget_cells":int(len(regrets)),
        "benchmark_point_below_r2_bound_count":int(
            regrets.benchmark_point_below_r2_bound.sum()
        ),
        "source_winner_equals_target_best_count":int(
            regrets.source_winner_equals_target_best.sum()
        ),
        "descriptive_portable_contradictions":int(
            tolerances.descriptive_portable_contradiction.sum()
        ),
    }
    (out/"criteo_r3_r2_comparison.json").write_text(
        json.dumps(comparison,indent=2),encoding="utf-8"
    )

    techcols=[
        "r2_policy_rates_reproduced_absdiff_le_1e12",
        "all_target_infer_policy_rates_within_005",
        "target_propensity_overlap_pass",
        "target_propensity_calibration_large_pass_le_002",
        "target_propensity_max_bin_calibration_pass_le_01",
        "target_weighted_balance_pass_max_smd_le_02",
        "target_outcome_nuisance_event_support_pass",
        "all_benchmark_contrasts_finite",
        "benchmark_corr_psd_numeric_pass",
    ]
    summary={
        "stage":"Criteo R3 Frozen Target-Outcome Benchmark",
        "r1_source_sha256":r1sha,
        "r2_pairwise_sha256":EXPECTED_R2_PAIR_SHA256,
        "r2_bounds_sha256":EXPECTED_R2_BOUND_SHA256,
        "r2_rules_sha256":EXPECTED_R2_RULE_SHA256,
        "r2_ratio_audit_sha256":EXPECTED_R2_RATIO_SHA256,
        "r2_summary_sha256":EXPECTED_R2_SUMMARY_SHA256,
        "benchmark_estimator":"target-only AIPW on target_infer; target-adapt nuisance training",
        "benchmark_sensitivity":"target-only propensity-adjusted IPW",
        "r2_outputs_modified_after_unlock":False,
        "all_r3_technical_gates_pass":bool(gates[techcols].all(axis=None)),
        "comparison_metrics_are_descriptive_not_gates":True,
        "criteo_role":"secondary large-scale real-data application/benchmark",
        "next_if_technical_pass":"Forensic review of benchmark agreement, then R4 robustness/manuscript evidence freeze.",
    }
    (out/"criteo_r3_summary.json").write_text(
        json.dumps(summary,indent=2),encoding="utf-8"
    )

    print("\\n=== R3 TARGET REGRET BENCHMARK ===")
    print(regrets.to_string(index=False))
    print("\\n=== R3 R2-vs-TARGET COMPARISON ===")
    print(comparison)
    print("\\n=== R3 TARGET NUISANCE AUDIT ===")
    print(props.to_string(index=False))
    print("\\n=== R3 TECHNICAL GATE ===")
    print(gates.to_string(index=False))
    print("\\nSummary:",summary)
    print("\\nFinished. Results:",out)


if __name__=="__main__":
    main()
