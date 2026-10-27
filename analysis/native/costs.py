"""Illustrative cost metrics: whole-run (v1-compatible) and windowed steady-state (v2 new).

SYNTHETIC educational data. Cost rates are assumptions, never salaries or real prices.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .parsing import SCENARIOS, require

COST_RATES = dict(zip(range(1, 6), [20., 35., 45., 30., 20.]))


def fieller_ratio(numerator, denominator):
    """Paired Fieller interval for a ratio of two paired replication means."""
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
    low, high = sorted([(-b - math.sqrt(discriminant)) / (2 * a),
                        (-b + math.sqrt(discriminant)) / (2 * a)])
    return dict(status="finite_positive_savings", estimate=mean_n / mean_d,
                ci95_low=float(low), ci95_high=float(high))


def hypothetical_costs(frame, effects):
    """Whole-run cost per saved order-lead-hour, matching v1's definition (entire campaign)."""
    baseline = frame[frame.scenario == 0].set_index("seed").sort_index()
    rows = []
    for scenario, rate in COST_RATES.items():
        alternative = frame[frame.scenario == scenario].set_index("seed")
        if alternative.empty:
            continue
        alternative = alternative.loc[baseline.index.intersection(alternative.index)]
        base = baseline.loc[alternative.index]
        lead = base.mean_lead_h - alternative.mean_lead_h
        cost = rate * alternative.final_time_h if "final_time_h" in alternative else rate * np.nan
        saved_hours = base.target * lead if "target" in base else np.nan
        ratio = fieller_ratio(cost, saved_hours)
        gain = effects[(effects.scenario == scenario) & (effects.metric == "throughput_per_h")]
        positive_gain = bool(not gain.empty and gain.iloc[0].ci95_low is not None
                             and gain.iloc[0].ci95_low > 0)
        gain_row = gain.iloc[0] if not gain.empty else None
        rows.append(dict(scenario=scenario, scenario_name=SCENARIOS[scenario], added_cost_rate=rate,
                         cost_rate_units="illustrative currency/model-hour",
                         mean_campaign_cost=float(cost.mean()),
                         mean_saved_order_lead_hours=float(saved_hours.mean()),
                         lead_savings_cost_units="illustrative currency/accumulated order-lead-hour saved",
                         lead_savings_ratio_status=ratio["status"], lead_savings_ratio=ratio["estimate"],
                         lead_savings_ratio_ci95_low=ratio["ci95_low"],
                         lead_savings_ratio_ci95_high=ratio["ci95_high"],
                         incremental_unit_cost_status=("finite_positive_gain" if positive_gain
                                                       else "undefined_gain_ci_includes_zero_or_negative"),
                         incremental_unit_cost=rate / gain_row["mean"] if positive_gain else None,
                         incremental_unit_cost_ci95_low=rate / gain_row.ci95_high if positive_gain else None,
                         incremental_unit_cost_ci95_high=rate / gain_row.ci95_low if positive_gain else None))
    return rows


def windowed_cost_per_station_hour(windowed_frame):
    """Cost per added station-hour in the steady-state window: just the illustrative rate,
    reported per scenario for traceability (Â§7 preregistration: this is the ratio numerator)."""
    rows = []
    for scenario, rate in COST_RATES.items():
        group = windowed_frame[windowed_frame.scenario == scenario]
        if group.empty:
            continue
        rows.append(dict(scenario=scenario, scenario_name=SCENARIOS[scenario],
                         added_cost_rate_per_h=rate,
                         mean_window_hours=float(group.window_hours.mean())))
    return rows


def windowed_cost_per_lead_hour_saved(windowed_frame, windowed_effects):
    """Cost per order-lead-hour saved, evaluated on the windowed (post-warm-up) cohort only."""
    baseline = windowed_frame[windowed_frame.scenario == 0].set_index("seed").sort_index()
    rows = []
    for scenario, rate in COST_RATES.items():
        alternative = windowed_frame[windowed_frame.scenario == scenario].set_index("seed")
        if alternative.empty:
            continue
        alternative = alternative.loc[baseline.index.intersection(alternative.index)]
        base = baseline.loc[alternative.index]
        lead_reduction = base.mean_lead_h - alternative.mean_lead_h
        # Windowed completed orders implied by windowed throughput * windowed hours.
        completed = alternative.throughput_per_h * alternative.window_hours
        cost = rate * alternative.window_hours
        saved_hours = completed * lead_reduction
        ratio = fieller_ratio(cost, saved_hours)
        gain = windowed_effects[(windowed_effects.scenario == scenario)
                                & (windowed_effects.metric == "throughput_per_h")]
        positive_gain = bool(not gain.empty and gain.iloc[0].ci95_low is not None
                             and gain.iloc[0].ci95_low > 0 and lead_reduction.mean() > 0
                             and ratio["status"] == "finite_positive_savings")
        rows.append(dict(scenario=scenario, scenario_name=SCENARIOS[scenario],
                         added_cost_rate_per_h=rate, windowed=True,
                         mean_windowed_cost=float(cost.mean()),
                         mean_windowed_saved_order_lead_hours=float(saved_hours.mean()),
                         windowed_lead_savings_ratio_status=(ratio["status"] if positive_gain else "undefined_preregistered_throughput_gain_gate"),
                         windowed_lead_savings_ratio=(ratio["estimate"] if positive_gain else None),
                         windowed_lead_savings_ratio_ci95_low=(ratio["ci95_low"] if positive_gain else None),
                         windowed_lead_savings_ratio_ci95_high=(ratio["ci95_high"] if positive_gain else None),
                         descriptive_lead_hours_only_ratio=ratio["estimate"],
                         descriptive_lead_hours_only_ci95_low=ratio["ci95_low"],
                         descriptive_lead_hours_only_ci95_high=ratio["ci95_high"],
                         positive_gain_required_and_met=positive_gain))
    return rows
