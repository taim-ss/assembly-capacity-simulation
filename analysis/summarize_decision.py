"""Synthesize validated native P3 outputs; never generate simulation observations."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from analyze_native import METRICS, SCENARIOS, STAGES, confidence, require

ROOT = Path(__file__).resolve().parents[1]
COST_RATES = dict(zip(range(1, 6), [20., 35., 45., 30., 20.]))
ABS_TOLERANCES = dict(zip(METRICS, [.5, .5, .25, .001]))
SENSITIVITIES = {
    "arrival-25": ("sensitivity-arrival-25", 25., 1.),
    "arrival-40": ("sensitivity-arrival-40", 40., 1.),
    "service-0.75": ("sensitivity-service-0.75", 30., .75),
    "service-1.25": ("sensitivity-service-1.25", 30., 1.25),
}


def load_bundle(folder: Path, seeds: list[int], interarrival=30., scale=1.):
    """Require a complete previously validated native matrix and record input hashes."""
    filenames = ["native_analysis.json", "replications.csv", "station_replications.csv"]
    missing = [str(folder / name) for name in filenames if not (folder / name).is_file()]
    require(not missing, f"Missing analyzed native inputs: {missing}")
    metadata = json.loads((folder / filenames[0]).read_text(encoding="utf-8"))
    require(metadata.get("mode") == "finite" and "actual AnyLogic native output" in metadata.get("label", ""),
            f"Not validated finite native output: {folder}")
    configuration = metadata.get("configuration", {})
    require(configuration.get("interarrival") == interarrival and configuration.get("scale") == scale,
            f"Input settings mismatch: {folder}")
    frame = pd.read_csv(folder / "replications.csv")
    stations = pd.read_csv(folder / "station_replications.csv")
    required = {"seed", "scenario", "target", "final_time_h", *METRICS}
    require(required.issubset(frame.columns), "Invalid native replication columns")
    expected = {(seed, scenario) for seed in seeds for scenario in range(6)}
    observed = list(zip(frame.seed, frame.scenario))
    require(len(observed) == len(set(observed)) and set(observed) == expected,
            f"Incomplete/duplicate native replication matrix: {folder}")
    require(np.isfinite(frame[list(required)].to_numpy(dtype=float)).all()
            and frame.target.eq(600).all() and frame.final_time_h.gt(0).all(), "Invalid native estimates")
    manifest_keys = [(item["seed"], item["scenario"]) for item in metadata.get("inputs", [])]
    require(len(manifest_keys) == len(expected) and set(manifest_keys) == expected,
            "Native provenance manifest does not match estimates")
    station_columns = ["utilization", "mean_queue", "empty_station_idle_fraction"]
    require({"seed", "scenario", "stage", *station_columns}.issubset(stations.columns),
            "Invalid station columns")
    station_keys = list(zip(stations.seed, stations.scenario, stations.stage))
    require(len(station_keys) == len(set(station_keys))
            and set(station_keys) == {(s, k, stage) for s, k in expected for stage in STAGES},
            "Incomplete/duplicate native station matrix")
    require(np.isfinite(stations[station_columns].to_numpy()).all(), "Invalid station estimates")
    hashes = [dict(path=str((folder / name).resolve()),
                   sha256=hashlib.sha256((folder / name).read_bytes()).hexdigest()) for name in filenames]
    return frame, stations, hashes


def precision(values, metric):
    """Expose both declared tests; no post-hoc threshold defines 'near zero'."""
    result = confidence(values)
    half = result["half_width"]
    tolerance = ABS_TOLERANCES[metric]
    result.update(absolute_tolerance=tolerance,
                  absolute_precision_met=bool(half is not None and half <= tolerance),
                  ci_excludes_zero=bool(result["ci95_low"] is not None
                                        and (result["ci95_low"] > 0 or result["ci95_high"] < 0)))
    return result


def holm_adjust(pvalues):
    """Holm family adjustment for all five alternatives within one KPI."""
    adjusted = np.empty(len(pvalues))
    previous = 0.
    for rank, index in enumerate(np.argsort(pvalues)):
        previous = max(previous, min(1., (len(pvalues) - rank) * pvalues[index]))
        adjusted[index] = previous
    return adjusted


def paired_effects(frame):
    baseline = frame[frame.scenario == 0].set_index("seed").sort_index()
    rows = []
    for metric in METRICS:
        family = []
        for scenario in range(1, 6):
            alternative = frame[frame.scenario == scenario].set_index("seed").loc[baseline.index]
            values = (alternative[metric] - baseline[metric] if metric == "throughput_per_h"
                      else baseline[metric] - alternative[metric])
            deviation = float(values.std(ddof=1))
            pvalue = (float(2 * stats.t.sf(abs(values.mean()) / (deviation / np.sqrt(len(values))), len(values)-1))
                      if deviation > 0 else (1. if values.mean() == 0 else 0.))
            family.append(dict(scenario=scenario, scenario_name=SCENARIOS[scenario], metric=metric,
                               positive_means="alternative improvement over baseline", p_two_sided=pvalue,
                               **precision(values, metric)))
        for row, adjusted in zip(family, holm_adjust([r["p_two_sided"] for r in family])):
            row.update(holm_p=float(adjusted), holm_reject_005=bool(adjusted < .05))
        rows.extend(family)
    return pd.DataFrame(rows)


def compare_assembly_test(frame):
    assembly = frame[frame.scenario == 2].set_index("seed").sort_index()
    test = frame[frame.scenario == 3].set_index("seed").loc[assembly.index]
    return pd.DataFrame([dict(metric=metric, positive_means="Test +1 improves over Assembly +1",
                              **precision(assembly[metric] - test[metric], metric))
                         for metric in METRICS[:3]])


def fieller_ratio(numerator, denominator):
    """Paired Fieller interval for ratio of mean campaign cost to mean saved order-hours."""
    numerator, denominator = np.asarray(numerator), np.asarray(denominator)
    n = len(numerator)
    require(n == len(denominator) and n > 1, "Ratio requires matched independent replications")
    mean_n, mean_d = float(numerator.mean()), float(denominator.mean())
    covariance = np.cov(numerator, denominator, ddof=1) / n
    t2 = stats.t.ppf(.975, n - 1) ** 2
    a = mean_d ** 2 - t2 * covariance[1, 1]
    b = -2 * (mean_n * mean_d - t2 * covariance[0, 1])
    c = mean_n ** 2 - t2 * covariance[0, 0]
    discriminant = b * b - 4 * a * c
    if mean_d <= 0 or a <= 0 or discriminant < 0:
        return dict(status="undefined_or_unbounded", estimate=None, ci95_low=None, ci95_high=None)
    low, high = sorted([(-b - math.sqrt(discriminant)) / (2*a),
                        (-b + math.sqrt(discriminant)) / (2*a)])
    return dict(status="finite_positive_savings", estimate=mean_n / mean_d,
                ci95_low=float(low), ci95_high=float(high))


def hypothetical_costs(frame, effects):
    baseline = frame[frame.scenario == 0].set_index("seed").sort_index()
    rows = []
    for scenario, rate in COST_RATES.items():
        alternative = frame[frame.scenario == scenario].set_index("seed").loc[baseline.index]
        lead = baseline.mean_lead_h - alternative.mean_lead_h
        cost = rate * alternative.final_time_h
        saved_hours = baseline.target * lead
        ratio = fieller_ratio(cost, saved_hours)
        gain = effects[(effects.scenario == scenario) & (effects.metric == "throughput_per_h")].iloc[0]
        positive_gain = gain.ci95_low > 0
        rows.append(dict(scenario=scenario, scenario_name=SCENARIOS[scenario], added_cost_rate=rate,
                         cost_rate_units="illustrative currency/model-hour", mean_campaign_cost=float(cost.mean()),
                         mean_saved_order_lead_hours=float(saved_hours.mean()),
                         lead_savings_cost_units="illustrative currency/accumulated order-lead-hour saved",
                         lead_savings_ratio_status=ratio["status"], lead_savings_ratio=ratio["estimate"],
                         lead_savings_ratio_ci95_low=ratio["ci95_low"], lead_savings_ratio_ci95_high=ratio["ci95_high"],
                         incremental_unit_cost_status="finite_positive_gain" if positive_gain else "undefined_gain_ci_includes_zero_or_negative",
                         incremental_unit_cost=rate/gain["mean"] if positive_gain else None,
                         incremental_unit_cost_ci95_low=rate/gain.ci95_high if positive_gain else None,
                         incremental_unit_cost_ci95_high=rate/gain.ci95_low if positive_gain else None,
                         incremental_unit_cost_units="illustrative currency/additional completed order; finite drain-rate gain only"))
    return pd.DataFrame(rows)


def station_evidence(stations):
    rows = []
    for (scenario, stage), group in stations.groupby(["scenario", "stage"], sort=True):
        for metric in ["utilization", "mean_queue", "empty_station_idle_fraction"]:
            rows.append(dict(scenario=int(scenario), stage=stage, metric=metric, **confidence(group[metric])))
    table = pd.DataFrame(rows)
    baseline = table[table.scenario == 0]
    utilization = baseline[baseline.metric == "utilization"].sort_values("mean", ascending=False)
    queues = baseline[baseline.metric == "mean_queue"].sort_values("mean", ascending=False)
    highest = utilization.iloc[0].stage
    index = STAGES.index(highest)
    downstream = STAGES[index+1] if index+1 < len(STAGES) else None
    downstream_idle = baseline[(baseline.stage == downstream) & (baseline.metric == "empty_station_idle_fraction")]
    narrative = dict(highest_baseline_utilization_stage=highest,
                     highest_baseline_queue_stage=queues.iloc[0].stage,
                     queue_definition="Queue immediately before that station's service",
                     next_downstream_stage=downstream,
                     next_downstream_empty_idle_fraction=None if downstream_idle.empty else float(downstream_idle.iloc[0]["mean"]),
                     interpretation="Descriptive whole-run utilization, upstream queue and downstream empty-idle proxy; not causal bottleneck proof. Infinite buffers have no downstream blocking.")
    return table, narrative


def create_outputs(confirmation, pilot, sensitivities, destination, hashes):
    frame, stations = confirmation
    effects = paired_effects(frame)
    direct = compare_assembly_test(frame)
    costs = hypothetical_costs(frame, effects)
    station_table, evidence = station_evidence(stations)
    means = pd.DataFrame([dict(scenario=int(scenario), scenario_name=SCENARIOS[scenario], metric=metric,
                               **precision(group[metric], metric))
                          for scenario, group in frame.groupby("scenario") for metric in METRICS])
    sensitivity = pd.concat([paired_effects(values).assign(setting=name)
                             for name, values in sensitivities.items()], ignore_index=True)
    lead_rows = effects[effects.metric == "mean_lead_h"].sort_values("mean", ascending=False)
    defined_costs = costs[costs.lead_savings_ratio.notna()].sort_values("lead_savings_ratio")
    notes = dict(label="SYNTHETIC | actual native AnyLogic derived outputs; hypothetical assumptions",
                 headline="Independent confirmation only: seeds 11..200, 190 paired replications per configuration",
                 pilot="Seeds 1..10 remain exploratory and are not pooled with confirmation",
                 estimand="Finite 600-order campaign, initially empty and fully drained; no steady-state or industrial validation claim",
                 ranking_status="Nominal point-estimate rankings; scenario CIs are pointwise, Holm tests cover five baseline comparisons separately within each metric, not all metrics or scenario rankings",
                 nominal_largest_mean_lead_reduction=lead_rows.iloc[0].scenario_name,
                 nominal_lowest_cost_per_saved_order_lead_hour=None if defined_costs.empty else defined_costs.iloc[0].scenario_name,
                 precision_rule="Relative half-width <5% is reported separately from declared absolute tolerances (lead 0.5h, WIP 0.25 orders, throughput 0.001 orders/h). No post-hoc near-zero cutoff and no blanket precision-pass claim.",
                 costs="Rates [20,35,45,30,20] currency/h are assumptions. Pay added station for the whole alternative campaign; total cost / total order-lead-hours saved is a ratio of paired replication means with a Fieller 95% interval under approximate joint-normal means. Throughput ratio intervals invert the positive paired gain CI; drain-rate effects are not sustained productivity gains.",
                 station_evidence=evidence, input_hashes=hashes,
                 input_chain="Hashes cover analyzed CSVs and analyzer manifests, which retain source native-log paths and hashes. This helper does not run a simulator.",
                 direct_assembly_vs_test=json.loads(direct.to_json(orient="records")),
                 confirmation_alternatives=json.loads(effects.to_json(orient="records")),
                 hypothetical_costs=json.loads(costs.to_json(orient="records")))
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in [("confirmation_estimates", means), ("confirmation_alternatives", effects),
                        ("assembly_vs_test", direct), ("hypothetical_costs", costs),
                        ("station_evidence", station_table), ("sensitivity_alternatives", sensitivity),
                        ("exploratory_pilot_alternatives", paired_effects(pilot))]:
        table.to_csv(destination / f"{name}.csv", index=False)
    (destination / "decision.json").write_text(json.dumps(notes, indent=2, allow_nan=False), encoding="utf-8")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    for ax, metric in zip(axes, METRICS[:2]):
        selected = effects[effects.metric == metric]
        ax.errorbar(selected["mean"], range(5), xerr=selected.half_width, fmt="o", capsize=4)
        ax.set_yticks(range(5), selected.scenario_name)
        ax.axvline(0, color="gray", linewidth=.8)
        ax.set(title=metric, xlabel="Baseline minus alternative (h); pointwise paired 95% CI")
    fig.suptitle("SYNTHETIC | Independent confirmation, seeds 11-200 | finite 600-order campaigns")
    fig.savefig(destination / "confirmation_capacity_effects.png", dpi=160)
    plt.close(fig)
    return notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--output", type=Path, default=ROOT / "results/decision")
    args = parser.parse_args(argv)
    confirmation, stations, hashes = load_bundle(args.results / "native-confirmation", list(range(11, 201)))
    pilot, _, pilot_hashes = load_bundle(args.results / "native-analysis", list(range(1, 11)))
    hashes.extend(pilot_hashes)
    sensitivity = {}
    for name, (directory, interarrival, scale) in SENSITIVITIES.items():
        values, _, sources = load_bundle(args.results / directory, list(range(1, 11)), interarrival, scale)
        sensitivity[name] = values
        hashes.extend(sources)
    notes = create_outputs((confirmation, stations), pilot, sensitivity, args.output, hashes)
    print(f"Native decision outputs: {args.output.resolve()}")
    print(f"Nominal lead reduction ranking leader: {notes['nominal_largest_mean_lead_reduction']}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(f"Decision synthesis rejected: {error}") from error
