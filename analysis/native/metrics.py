"""Confidence intervals, windowed steady-state metrics, and bottleneck evidence.

SYNTHETIC educational data. Windowed metrics delete the first `warmup_jobs` jobs (by release
order / job index) per the Welch-derived warm-up, per `docs/v2-preregistration.md` section 7.
Station integrals are reconstructed exactly from native entered/started/finished timestamps,
including all rework visits. WIP includes waiting for components.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .parsing import STAGES, require


def confidence(values):
    values = np.asarray(values, dtype=float)
    n = len(values)
    mean = float(np.mean(values))
    half = float(stats.t.ppf(.975, n - 1) * stats.sem(values)) if n > 1 else None
    relative = half / abs(mean) if half is not None and abs(mean) > 1e-12 else None
    return dict(n=n, mean=mean, ci95_low=None if half is None else mean - half,
                ci95_high=None if half is None else mean + half, half_width=half,
                relative_half_width=relative,
                precision_under_5pct=bool(relative is not None and relative < .05),
                precision_status=("undefined_near_zero" if abs(mean) <= 1e-12 else
                                  "insufficient_replications" if n < 2 else
                                  "target_met" if relative < .05 else "more_replications_needed"))


def _interpolate(history, t):
    """`history`: sorted [(t, value), ...]. Linear-interpolate `value` at time `t`."""
    if not history:
        return 0.0
    if t <= history[0][0]:
        return history[0][1] * (t / history[0][0]) if history[0][0] > 0 else history[0][1]
    for (t1, a1), (t2, a2) in zip(history, history[1:]):
        if t <= t2:
            return a1 if t2 == t1 else a1 + (t - t1) / (t2 - t1) * (a2 - a1)
    return history[-1][1]


def windowed_metrics(run, warmup_jobs, target):
    """Windowed (post-warm-up) lead/P90/throughput/WIP and per-stage station metrics for one run."""
    require(0 <= warmup_jobs < target, "warmup_jobs must be within [0, target)")
    orders = run["orders"]
    horizon = run["done"][2]
    window_start = orders[warmup_jobs][0]
    window_hours = horizon - window_start
    require(window_hours > 0, "Warm-up boundary leaves no observation window")

    windowed_leads = [orders[j][2] for j in range(warmup_jobs, target)]
    n_windowed = len(windowed_leads)
    windowed_throughput = n_windowed / window_hours

    from .intervals import station_integrals, wip_area
    from .validation import scenario_capacities
    from .parsing import STAGES
    c=run["config"]
    caps=scenario_capacities(tuple(c["cap_"+s] for s in STAGES),run["key"][1])
    areas=station_integrals(run,caps,window_start,horizon)
    station_rows=[]
    for stage,name in enumerate(STAGES):
        busy,queue,idle,starved,idle_units=areas[stage]
        station_rows.append(dict(stage=name,window_busy_area=busy,window_queue_area=queue,
          window_starved_area=starved,window_idle_units_area=idle_units,window_hours=window_hours))
    windowed_wip=wip_area(run,window_start,horizon)/window_hours
    return dict(warmup_jobs=warmup_jobs, window_start_h=window_start, window_hours=window_hours,
               n_windowed_jobs=n_windowed, windowed_mean_lead_h=float(np.mean(windowed_leads)),
               windowed_p90_lead_h=float(np.quantile(windowed_leads, .9)),
               windowed_throughput_per_h=windowed_throughput, windowed_wip=windowed_wip,
               stations=station_rows)


def windowed_matrix(runs, capacities_by_key, warmup_jobs, target):
    """Build replication- and station-level windowed DataFrames across many runs.

    `capacities_by_key`: {(seed, scenario): (cap_Kitting,...,cap_Handover)} for utilization.
    """
    reps, stations = [], []
    for run in runs:
        seed, scenario = run["key"]
        result = windowed_metrics(run, warmup_jobs, target)
        reps.append(dict(seed=seed, scenario=scenario,
                         mean_lead_h=result["windowed_mean_lead_h"],
                         p90_lead_h=result["windowed_p90_lead_h"],
                         mean_wip=result["windowed_wip"],
                         throughput_per_h=result["windowed_throughput_per_h"],
                         window_hours=result["window_hours"], warmup_jobs=warmup_jobs))
        caps = capacities_by_key[(seed, scenario)]
        for row, capacity in zip(result["stations"], caps):
            stations.append(dict(seed=seed, scenario=scenario, stage=row["stage"],
                                 capacity=capacity,
                                 utilization=row["window_busy_area"] / (capacity * row["window_hours"]),
                                 mean_queue=row["window_queue_area"] / row["window_hours"],
                                 starved_by_upstream_fraction=row["window_starved_area"] / row["window_hours"],
                                 idle_units_mean=row["window_idle_units_area"] / row["window_hours"]))
    return pd.DataFrame(reps), pd.DataFrame(stations)


def bottleneck_table(stations, scenarios_of_interest):
    """Per-scenario bottleneck call: highest utilization AND elevated queue AND downstream
    starvation must agree, else the scenario is reported 'ambiguous/moving bottleneck'.
    `scenarios_of_interest`: {scenario_int: label} to include, e.g. {0: 'Baseline', 2: 'Assembly +1'}.
    """
    rows = []
    for scenario, label in scenarios_of_interest.items():
        group = stations[stations.scenario == scenario]
        if group.empty:
            continue
        by_stage = group.groupby("stage").agg(
            utilization=("utilization", "mean"), mean_queue=("mean_queue", "mean"),
            starved_by_upstream_fraction=("starved_by_upstream_fraction", "mean")).reindex(STAGES)
        top_util_stage = by_stage.utilization.idxmax()
        top_queue_stage = by_stage.mean_queue.idxmax()
        index = STAGES.index(top_util_stage)
        downstream = STAGES[index + 1] if index + 1 < len(STAGES) else None
        downstream_starved = (float(by_stage.loc[downstream, "starved_by_upstream_fraction"])
                              if downstream else None)
        agrees = (top_util_stage == top_queue_stage
                 and downstream_starved is not None and downstream_starved > 0.01)
        rows.append(dict(scenario=scenario, scenario_label=label,
                         highest_utilization_stage=top_util_stage,
                         highest_utilization=float(by_stage.utilization.max()),
                         highest_queue_stage=top_queue_stage,
                         highest_queue=float(by_stage.mean_queue.max()),
                         downstream_of_top_utilization=downstream,
                         downstream_starved_by_upstream_fraction=downstream_starved,
                         bottleneck_call=(top_util_stage if agrees else "ambiguous/moving bottleneck"),
                         evidence_agrees=bool(agrees)))
    table = pd.DataFrame(rows)
    moved = (table.shape[0] > 1
            and table.bottleneck_call.nunique() > 1
            and not table.bottleneck_call.eq("ambiguous/moving bottleneck").all())
    return table, dict(bottleneck_moves_across_scenarios=bool(moved))
