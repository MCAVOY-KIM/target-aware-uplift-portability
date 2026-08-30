from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EXPECTED = {'r2_pairwise': '5949d500efbc74a0fe033f81eb47ed6374f158c378b64d453ffa240c398b7a23', 'r2_bounds': '674ffed3be874de1fb6c76f376d6d726288dc9eaefdeb4e99d656888dcd3cbba', 'r2_tolerance': '26f75b46c669d85620f35034d3d5ddbf9ead50a36df47e0948f79e4c2d21c479', 'r2_ratio': '2b01c556a943ce9fecdde1a7543b60c1aa78840f61fd6196cb04b0587e38138a', 'r3_regret': '599628ec5ae6bb1256d3a0a721dae0facdee7f54fef0847f67b3def6128dbbde', 'r3_pairs': 'd854ba2fec73aeebac5a72abb623bd7294aa199be643dcdfbc7442fcf7e1b653', 'r3_gains': '0ca905d88d1020036c354d30d8a28067d00f64e206172fffda839c8d321b1fc8', 'r3_tolerance': 'cce8d38a404c34cbf5b1121b6f67e9b9d53b9128b40374bfb97b82f736c1f8df', 'r3_audit': 'cc8632961d61732de7bba09c5486ea861ce59570aa247c113ed26eadd3125053', 'r3_gate': '2dce7faa555bc15ab565835289276ef02e8e1190514cd3fcf77df49aa5079f08'}

SCENARIO_ORDER = ["null_ess1.0","pc1_ess0.8","pc1_ess0.5"]
SCENARIO_LABEL = {
    "null_ess1.0":"No shift (ESS=1.0)",
    "pc1_ess0.8":"Moderate shift (ESS≈0.8)",
    "pc1_ess0.5":"Stronger shift (ESS≈0.5)",
}


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path: Path, key: str):
    got = sha(path)
    exp = EXPECTED[key]
    if got != exp:
        raise RuntimeError(f"Frozen artifact changed: {key} expected={exp} got={got}")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--r2-outdir",required=True)
    ap.add_argument("--r3-outdir",required=True)
    ap.add_argument("--outdir",required=True)
    args=ap.parse_args()

    r2=Path(args.r2_outdir).resolve()
    r3=Path(args.r3_outdir).resolve()
    out=Path(args.outdir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    figs=out/"figures"; figs.mkdir(exist_ok=True)
    tables=out/"tables"; tables.mkdir(exist_ok=True)

    files={
        "r2_pairwise":r2/"criteo_r2_pairwise_contrasts.csv",
        "r2_bounds":r2/"criteo_r2_portability_bounds.csv",
        "r2_tolerance":r2/"criteo_r2_tolerance_frontier.csv",
        "r2_ratio":r2/"criteo_r2_ratio_inference_audit.csv",
        "r3_regret":r3/"criteo_r3_regret_benchmark.csv",
        "r3_pairs":r3/"criteo_r3_target_pairwise_benchmark.csv",
        "r3_gains":r3/"criteo_r3_target_benchmark_gains.csv",
        "r3_tolerance":r3/"criteo_r3_tolerance_benchmark.csv",
        "r3_audit":r3/"criteo_r3_target_nuisance_audit.csv",
        "r3_gate":r3/"criteo_r3_gate.csv",
    }
    for k,p in files.items():
        verify(p,k)

    rb=pd.read_csv(files["r2_bounds"])
    rp=pd.read_csv(files["r2_pairwise"])
    rr=pd.read_csv(files["r3_regret"])
    rpair=pd.read_csv(files["r3_pairs"])
    rg=pd.read_csv(files["r3_gains"])
    rt=pd.read_csv(files["r3_tolerance"])
    ratio=pd.read_csv(files["r2_ratio"])
    audit=pd.read_csv(files["r3_audit"])
    gate=pd.read_csv(files["r3_gate"])

    # Main nine-cell manuscript table.
    main=rr.copy()
    source_gain=[]
    best_gain=[]
    relative_regret=[]
    resolved=[]
    for _,r in main.iterrows():
        g=rg[(rg.scenario==r.scenario)&np.isclose(rg.budget,r.budget)]
        sg=float(g[g.model==r.source_winner].target_aipw_gain.iloc[0])
        bg=float(g.target_aipw_gain.max())
        source_gain.append(sg)
        best_gain.append(bg)
        relative_regret.append(float(r.target_benchmark_point_regret/bg) if bg!=0 else np.nan)
        resolved.append(bool(r.target_benchmark_lower_regret_95>0))
    main["source_winner_target_gain"]=source_gain
    main["target_best_gain"]=best_gain
    main["benchmark_regret_fraction_of_best_gain"]=relative_regret
    main["benchmark_resolved_nonzero_regret"]=resolved
    main["scenario_label"]=main.scenario.map(SCENARIO_LABEL)
    main["benchmark_regret_bp"]=main.target_benchmark_point_regret*10000
    main["r2_upper_bound_bp"]=main.r2_asymptotic_upper_regret_bound_95*10000
    main.to_csv(tables/"table_main_portability_evidence.csv",index=False)

    # Tolerance calibration table.
    tolrows=[]
    for eps,g in rt.groupby("epsilon",sort=True):
        portable=(g.r2_status=="PORTABLE_AT_TOLERANCE")
        uncertain=(g.r2_status=="UNCERTAIN")
        nonport=(g.r2_status=="EVIDENCE_OF_NON_PORTABILITY")
        bench=(g.target_benchmark_status=="BENCHMARK_REGRET_LE_TOLERANCE")
        contradiction=g.descriptive_portable_contradiction.astype(bool)
        conservative=(uncertain & bench)
        tolrows.append({
            "epsilon":eps,
            "epsilon_bp":eps*10000,
            "n_cells":len(g),
            "r2_portable":int(portable.sum()),
            "r2_uncertain":int(uncertain.sum()),
            "r2_nonportable":int(nonport.sum()),
            "benchmark_regret_le_tolerance":int(bench.sum()),
            "false_portable_contradictions":int(contradiction.sum()),
            "conservative_abstentions":int(conservative.sum()),
        })
    toltab=pd.DataFrame(tolrows)
    toltab.to_csv(tables/"table_tolerance_decisions.csv",index=False)

    # Pairwise agreement and sensitivity.
    d=rpair.r2_transported_delta-rpair.target_aipw_delta
    aipw_ipw=rpair.target_aipw_delta-rpair.target_ipw_delta_sensitivity
    pair_summary={
        "n_contrasts":int(len(rpair)),
        "r2_vs_target_mae":float(np.mean(np.abs(d))),
        "r2_vs_target_rmse":float(np.sqrt(np.mean(d*d))),
        "r2_vs_target_correlation":float(np.corrcoef(rpair.r2_transported_delta,rpair.target_aipw_delta)[0,1]),
        "r2_vs_target_sign_agreement":float(np.mean(np.sign(rpair.r2_transported_delta)==np.sign(rpair.target_aipw_delta))),
        "r2_upper_above_target_point_count":int((rpair.target_aipw_delta<=rpair.r2_upper_95_family).sum()),
        "r2_upper_above_target_point_fraction":float(np.mean(rpair.target_aipw_delta<=rpair.r2_upper_95_family)),
        "target_aipw_vs_ipw_mae":float(np.mean(np.abs(aipw_ipw))),
        "target_aipw_vs_ipw_rmse":float(np.sqrt(np.mean(aipw_ipw*aipw_ipw))),
        "target_aipw_vs_ipw_correlation":float(np.corrcoef(rpair.target_aipw_delta,rpair.target_ipw_delta_sensitivity)[0,1]),
        "target_aipw_vs_ipw_sign_agreement":float(np.mean(np.sign(rpair.target_aipw_delta)==np.sign(rpair.target_ipw_delta_sensitivity))),
    }
    (out/"pairwise_agreement_summary.json").write_text(json.dumps(pair_summary,indent=2),encoding="utf-8")

    # Nine-cell summary.
    nine={
        "source_winner_equals_point_estimated_target_best":int(main.source_winner_equals_target_best.sum()),
        "source_winner_differs_from_point_estimated_target_best":int((~main.source_winner_equals_target_best.astype(bool)).sum()),
        "benchmark_resolved_nonzero_regret_cells":int((main.target_benchmark_lower_regret_95>0).sum()),
        "benchmark_point_below_frozen_r2_bound":int(main.benchmark_point_below_r2_bound.sum()),
        "max_target_benchmark_point_regret":float(main.target_benchmark_point_regret.max()),
        "max_target_benchmark_point_regret_bp":float(main.benchmark_regret_bp.max()),
        "max_r2_upper_regret_bound":float(main.r2_asymptotic_upper_regret_bound_95.max()),
        "max_r2_upper_regret_bound_bp":float(main.r2_upper_bound_bp.max()),
        "nine_cell_point_regret_mae":float(np.mean(np.abs(main.r2_point_regret_hat-main.target_benchmark_point_regret))),
        "nine_cell_point_regret_correlation":float(np.corrcoef(main.r2_point_regret_hat,main.target_benchmark_point_regret)[0,1]),
        "min_r2_bound_minus_benchmark_point":float((main.r2_asymptotic_upper_regret_bound_95-main.target_benchmark_point_regret).min()),
        "all_target_ipw_regret_below_r2_bound":bool(np.all(main.target_ipw_regret_sensitivity<=main.r2_asymptotic_upper_regret_bound_95)),
    }
    (out/"nine_cell_summary.json").write_text(json.dumps(nine,indent=2),encoding="utf-8")

    # Diagnostics table.
    diag=ratio.merge(audit,on="scenario",suffixes=("_r2","_r3"))
    diag["scenario_label"]=diag.scenario.map(SCENARIO_LABEL)
    diag.to_csv(tables/"table_application_diagnostics.csv",index=False)

    # Figure 1: benchmark regret vs frozen R2 bound.
    plot=main.copy()
    plot["cell"]=plot.scenario.map({
        "null_ess1.0":"Null",
        "pc1_ess0.8":"ESS .8",
        "pc1_ess0.5":"ESS .5"
    })+" / q="+plot.budget.astype(str)
    x=np.arange(len(plot))
    fig,ax=plt.subplots(figsize=(11,5.5))
    ax.plot(x,plot.target_benchmark_point_regret*10000,marker="o",label="Held-out target benchmark regret")
    ax.plot(x,plot.r2_point_regret_hat*10000,marker="s",label="R2 transported point regret")
    ax.plot(x,plot.r2_asymptotic_upper_regret_bound_95*10000,marker="^",label="R2 asymptotic upper regret bound")
    ax.axhline(.0005*10000,linestyle="--",label="Tolerance ε=0.0005")
    ax.set_xticks(x)
    ax.set_xticklabels(plot.cell,rotation=45,ha="right")
    ax.set_ylabel("Regret (basis points of outcome probability)")
    ax.set_title("Frozen R2 Portability Assessment vs Held-out Target Benchmark")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figs/"figure_r2_vs_target_regret.png",dpi=220)
    plt.close(fig)

    # Figure 2: 45 directed contrast scatter.
    fig,ax=plt.subplots(figsize=(6.5,6.5))
    ax.scatter(rpair.r2_transported_delta*10000,rpair.target_aipw_delta*10000,s=28)
    vals=np.concatenate([rpair.r2_transported_delta.values,rpair.target_aipw_delta.values])*10000
    lo=float(vals.min()); hi=float(vals.max())
    ax.plot([lo,hi],[lo,hi],linestyle="--")
    ax.set_xlabel("R2 transported contrast (bp)")
    ax.set_ylabel("Held-out target AIPW contrast (bp)")
    ax.set_title("Pairwise Transported vs Held-out Target Contrasts")
    fig.tight_layout()
    fig.savefig(figs/"figure_pairwise_r2_vs_target.png",dpi=220)
    plt.close(fig)

    # Figure 3: relative practical regret.
    fig,ax=plt.subplots(figsize=(11,5.5))
    ax.bar(x,plot.benchmark_regret_fraction_of_best_gain*100)
    ax.set_xticks(x)
    ax.set_xticklabels(plot.cell,rotation=45,ha="right")
    ax.set_ylabel("Benchmark regret / point-estimated best target gain (%)")
    ax.set_title("Practical Cost of Reusing the Source-selected Model")
    fig.tight_layout()
    fig.savefig(figs/"figure_relative_regret.png",dpi=220)
    plt.close(fig)

    # Frozen evidence narrative.
    narrative=f"""# Criteo R4 Evidence Freeze

This stage performs no model fitting, no threshold selection, and no inference repair.
It only summarizes cryptographically frozen R2/R3 artifacts.

## Core empirical facts

- Point-estimated target-best model differs from the source-selected model in {nine['source_winner_differs_from_point_estimated_target_best']}/9 scenario-budget cells.
- Yet held-out target benchmark point regret is below .0005 in all 9 cells.
- The maximum benchmark point regret is {nine['max_target_benchmark_point_regret']:.9f} ({nine['max_target_benchmark_point_regret_bp']:.3f} bp).
- The frozen R2 asymptotic upper bound exceeds the held-out benchmark point regret in all 9 cells.
- At epsilon=.0005, R2 makes 7 portable decisions and 2 uncertain decisions; benchmark point regret is <= epsilon in all 9, so there are no false-portable contradictions and two conservative abstentions.
- At epsilon >= .001, all 9 R2 decisions are portable and all 9 benchmark point regrets remain below tolerance.
- Benchmark simultaneous lower regret bound is >0 in only {nine['benchmark_resolved_nonzero_regret_cells']}/9 cells. Thus point-estimated rank mismatch is much more common than statistically resolved practical inferiority.
- Across 45 directed contrasts, R2-vs-target correlation is {pair_summary['r2_vs_target_correlation']:.3f}, sign agreement is {pair_summary['r2_vs_target_sign_agreement']:.3f}, and the R2 one-sided upper contrast bound lies above the target benchmark point in {pair_summary['r2_upper_above_target_point_count']}/45 contrasts.
- Target-only IPW sensitivity regret is below the corresponding R2 bound in all nine cells.

## Interpretation discipline

Do not write that R2 'proved' portability or achieved exact 95% coverage.
The R2 bounds are asymptotic and the earlier rare-binary simulations found finite-sample undercoverage under stronger shift.

Do not write that source/target rankings were preserved. They were not.

The defensible empirical message is:

> The identity of the point-estimated best uplift model was unstable across independently evaluated populations, but this did not imply materially large deployment regret. The target-outcome-blind portability assessment distinguished rank disagreement from practical decision loss and, in this application, produced conservative or tolerance-consistent decisions relative to a held-out target-outcome benchmark.

Criteo remains a secondary large-scale application because the predeclared R1.2 propensity-balance gate narrowly failed in the two shifted scenarios.
"""
    (out/"R4_EVIDENCE_FREEZE.md").write_text(narrative,encoding="utf-8")

    summary={
        "stage":"Criteo R4 Frozen Evidence Synthesis",
        "new_model_fits":0,
        "new_method_tuning":False,
        "r2_or_r3_modified":False,
        "r3_all_technical_gates_pass":bool(gate.drop(columns=["scenario","target_outcomes_unlocked"]).all(axis=None)),
        "nine_cell_summary":nine,
        "pairwise_summary":pair_summary,
        "next":"Use these frozen tables/figures for manuscript evidence assessment; no additional Criteo repair unless a reproducibility defect is discovered.",
    }
    (out/"criteo_r4_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

    print("=== R4 NINE-CELL SUMMARY ===")
    print(json.dumps(nine,indent=2))
    print("\n=== R4 PAIRWISE SUMMARY ===")
    print(json.dumps(pair_summary,indent=2))
    print("\n=== R4 TOLERANCE TABLE ===")
    print(toltab.to_string(index=False))
    print("\nFinished:",out)


if __name__=="__main__":
    main()
