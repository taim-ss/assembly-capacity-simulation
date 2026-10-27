"""Write analyzed CSV/JSON/figure outputs for a validated native run matrix.

SYNTHETIC educational data. Mirrors v1's `analyze_native.write_outputs` for backward
compatibility, plus the v2 windowed/bottleneck/cost additions.
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .comparisons import summarize
from .mm1 import assess_mm1, assess_mmc
from .parsing import LABEL, METRICS, SCENARIOS


def write_outputs(runs, reps, stations, stages, destination, mode, replay_acceptance=None,
                  mmc_params=None, warmup_jobs=0):
    summary, comparisons = summarize(reps)
    if warmup_jobs:
        from .metrics import windowed_matrix,bottleneck_table
        from .validation import scenario_capacities
        from .parsing import STAGES
        from .comparisons import primary_contrast,paired_effects
        from .costs import windowed_cost_per_lead_hour_saved
        caps={r["key"]:scenario_capacities(tuple(r["config"]["cap_"+s] for s in STAGES),r["key"][1]) for r in runs}
        window_reps,window_stations=windowed_matrix(runs,caps,warmup_jobs,runs[0]["config"]["target"])
        destination.mkdir(parents=True,exist_ok=True)
        window_reps.to_csv(destination/"windowed_replications.csv",index=False)
        window_stations.to_csv(destination/"windowed_stations.csv",index=False)
        effects=paired_effects(window_reps)
        effects.to_csv(destination/"windowed_effects.csv",index=False)
        if {2,3}.issubset(set(window_reps.scenario)):
            primary_contrast(window_reps).to_csv(destination/"windowed_primary.csv",index=False)
        pd.DataFrame(windowed_cost_per_lead_hour_saved(window_reps,effects)).to_csv(destination/"windowed_costs.csv",index=False)
        bottleneck_table(window_stations,{0:"Baseline",2:"Assembly +1",3:"Test +1"})[0].to_csv(destination/"bottleneck.csv",index=False)

    station_summary = []
    station_metrics = ["utilization", "mean_queue", "empty_station_idle_fraction",
                       "starved_by_upstream_fraction", "idle_units_mean"]
    if not stations.empty:
        available = [m for m in station_metrics if m in stations.columns]
        for (scenario, stage), group in stations.groupby(["scenario", "stage"], sort=True):
            for metric in available:
                from .metrics import confidence
                station_summary.append(dict(scenario=int(scenario), stage=stage,
                                            metric=metric, **confidence(group[metric])))
    orders = pd.DataFrame([
        dict(seed=r["key"][0], scenario=r["key"][1], job_id=job, release_h=values[0],
             finish_h=values[1], lead_h=values[2], reworks=values[3])
        for r in runs for job, values in sorted(r["orders"].items())])
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in [("replications", reps), ("station_replications", stations),
                        ("stage_replications", stages), ("summary", summary),
                        ("paired_comparisons", comparisons), ("orders", orders),
                        ("station_summary", pd.DataFrame(station_summary))]:
        table.to_csv(destination / f"{name}.csv", index=False)
    notes = dict(label=LABEL, mode=mode, replay_source_acceptance=replay_acceptance,
                 configuration=runs[0]["config"], warmup_jobs=warmup_jobs,
                 experiment="finite terminating empty-to-drained; no warmup; not steady-state",
                 interval="Two-sided Student t 95% CI across independent replication estimates; paired by seed for alternatives. Individual replication P90 uses linear sample quantile.",
                 precision="Pilot n=10 by default. Flags assess each estimate separately; near-zero differences have undefined relative precision. No optional-stopping coverage guarantee; predeclare any further batch.",
                 station_idle="empty_station_idle_fraction is time station has zero busy and zero queued jobs divided by total run time; not per-resource-unit starvation and not causal bottleneck proof. starved_by_upstream_fraction (v2) is the real starvation proxy: time this stage is idle AND empty while its upstream queue is nonempty (the frozen feature-spec definition).",
                 wip="sum completed-job lead times / final time; all target jobs verified fully drained",
                 throughput="target / final time, including initial empty period and drain",
                 inputs=[dict(path=r["path"], sha256=r["sha256"], seed=r["key"][0], scenario=r["key"][1]) for r in runs],
                 summary=json.loads(summary.to_json(orient="records")),
                 paired_comparisons=json.loads(comparisons.to_json(orient="records")))
    if mode == "mm1":
        notes["mm1_verification"] = assess_mm1(reps)
        pd.DataFrame(notes["mm1_verification"]["checks"]).to_csv(destination / "mm1_verification.csv", index=False)
    if mode == "mmc":
        require_params = mmc_params or {}
        notes["mmc_verification"] = assess_mmc(reps, require_params.get("c", 3),
                                               require_params.get("lam"), require_params.get("mu"))
        pd.DataFrame(notes["mmc_verification"]["checks"]).to_csv(destination / "mmc_verification.csv", index=False)
    (destination / "native_analysis.json").write_text(json.dumps(notes, indent=2, allow_nan=False), encoding="utf-8")
    if not comparisons.empty:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
        for ax, metric, title in zip(axes, METRICS[:2], ["Mean lead reduction", "P90 lead reduction"]):
            data = comparisons[comparisons.metric == metric]
            positions = np.arange(len(data))
            ax.plot(data["mean"], positions, "o")
            intervals = data.half_width.notna()
            if intervals.any():
                ax.errorbar(data.loc[intervals, "mean"], positions[intervals.to_numpy()],
                            xerr=data.loc[intervals, "half_width"].astype(float), fmt="none", capsize=4)
            ax.set_yticks(positions, data.scenario_name)
            ax.axvline(0, color="gray", linewidth=.8)
            ax.set_title(title)
            interval_label = "paired 95% CI" if intervals.any() else "CI unavailable (n < 2)"
            ax.set_xlabel(f"Baseline minus alternative (hours); {interval_label}")
        fig.suptitle("SYNTHETIC | Actual AnyLogic finite terminating runs")
        fig.savefig(destination / "paired_lead_time.png", dpi=160)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    for scenario, group in orders.groupby("scenario", sort=True):
        ax.hist(group.lead_h, bins=30, density=True, histtype="step",
                label=SCENARIOS[scenario])
    ax.set(xlabel="Entire-run completed order lead time (hours)", ylabel="Density",
           title=f"SYNTHETIC | Actual AnyLogic {mode} output")
    ax.legend()
    fig.savefig(destination / "lead_time_histogram.png", dpi=160)
    plt.close(fig)
    return notes
