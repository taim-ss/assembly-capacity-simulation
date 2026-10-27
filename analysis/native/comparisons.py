"""Paired comparisons, Holm multiplicity adjustment, and the pre-registered primary contrast.

SYNTHETIC educational data. The primary confirmatory claim (per `docs/v2-preregistration.md`
section 6) is Assembly+1 vs Test+1 on mean and P90 lead time, Holm-adjusted across those two
tests only. Every other comparison here is exploratory and labelled pointwise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .metrics import confidence
from .parsing import METRICS, SCENARIOS, require

ABS_TOLERANCES = dict(zip(METRICS, [.5, .5, .25, .001]))


def precision(values, metric):
    """Expose both the relative and the absolute-tolerance test; no post-hoc 'near zero' cutoff."""
    result = confidence(values)
    half = result["half_width"]
    tolerance = ABS_TOLERANCES[metric]
    result.update(absolute_tolerance=tolerance,
                  absolute_precision_met=bool(half is not None and half <= tolerance),
                  ci_excludes_zero=bool(result["ci95_low"] is not None
                                        and (result["ci95_low"] > 0 or result["ci95_high"] < 0)))
    return result


def holm_adjust(pvalues):
    """Holm step-down family adjustment."""
    pvalues = np.asarray(pvalues, dtype=float)
    adjusted = np.empty(len(pvalues))
    previous = 0.
    for rank, index in enumerate(np.argsort(pvalues)):
        previous = max(previous, min(1., (len(pvalues) - rank) * pvalues[index]))
        adjusted[index] = previous
    return adjusted


def _two_sided_p(values):
    deviation = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    if deviation <= 0:
        return 1.0 if values.mean() == 0 else 0.0
    t_stat = abs(values.mean()) / (deviation / np.sqrt(len(values)))
    return float(2 * stats.t.sf(t_stat, len(values) - 1))


def summarize(frame):
    """Per-scenario KPI summaries and exploratory (baseline-paired) comparisons, as in v1."""
    summaries, comparisons = [], []
    for scenario, group in frame.groupby("scenario", sort=True):
        for metric in METRICS:
            summaries.append(dict(scenario=int(scenario), scenario_name=SCENARIOS[scenario],
                                  metric=metric, **confidence(group[metric])))
    baseline = frame[frame.scenario == 0].set_index("seed")
    for scenario in range(1, 6):
        alt = frame[frame.scenario == scenario].set_index("seed")
        if alt.empty:
            continue
        alt = alt.loc[baseline.index]
        for metric in METRICS:
            differences = (alt[metric] - baseline[metric] if metric == "throughput_per_h"
                           else baseline[metric] - alt[metric])
            comparisons.append(dict(scenario=scenario, scenario_name=SCENARIOS[scenario],
                                    metric=metric, positive_means="improvement",
                                    **confidence(differences)))
    return pd.DataFrame(summaries), pd.DataFrame(comparisons)


def paired_effects(frame):
    """Exploratory baseline-vs-each-alternative family, Holm-adjusted WITHIN each metric only
    (five alternatives per metric) — this is the v1-style exploratory table, not the primary
    confirmatory contrast (see `primary_contrast` below)."""
    baseline = frame[frame.scenario == 0].set_index("seed").sort_index()
    rows = []
    for metric in METRICS:
        family = []
        for scenario in range(1, 6):
            alternative = frame[frame.scenario == scenario].set_index("seed")
            if alternative.empty:
                continue
            alternative = alternative.loc[baseline.index.intersection(alternative.index)]
            paired_baseline = baseline.loc[alternative.index]
            values = (alternative[metric] - paired_baseline[metric] if metric == "throughput_per_h"
                      else paired_baseline[metric] - alternative[metric])
            family.append(dict(scenario=scenario, scenario_name=SCENARIOS[scenario], metric=metric,
                               positive_means="alternative improvement over baseline",
                               p_two_sided=_two_sided_p(values), **precision(values, metric)))
        for row, adjusted in zip(family, holm_adjust([r["p_two_sided"] for r in family])):
            row.update(holm_p=float(adjusted), holm_reject_005=bool(adjusted < .05))
        rows.extend(family)
    return pd.DataFrame(rows)


def compare_assembly_test(frame):
    """Exploratory, non-Holm direct comparison (kept for continuity with v1's reporting)."""
    assembly = frame[frame.scenario == 2].set_index("seed").sort_index()
    test = frame[frame.scenario == 3].set_index("seed").loc[assembly.index]
    return pd.DataFrame([dict(metric=metric, positive_means="Assembly +1 improves over Test +1",
                              **precision(test[metric] - assembly[metric]
                                         if metric != "throughput_per_h"
                                         else assembly[metric] - test[metric], metric))
                         for metric in METRICS[:3]])


def primary_contrast(frame):
    """The ONE Holm-adjusted confirmatory claim: Assembly+1 vs Test+1 on mean and P90 lead time.

    Positive = Assembly +1 has the shorter lead time (Test - Assembly, so positive favors
    Assembly, matching the brief's "Assembly+1 vs Test+1" framing).
    """
    assembly = frame[frame.scenario == 2].set_index("seed").sort_index()
    test = frame[frame.scenario == 3].set_index("seed").loc[assembly.index]
    require(len(assembly) == len(test) and len(assembly) > 1,
            "Primary contrast requires matched paired replications")
    rows = []
    for metric in ("mean_lead_h", "p90_lead_h"):
        diff = test[metric] - assembly[metric]
        rows.append(dict(metric=metric, positive_means="Assembly +1 shorter than Test +1",
                         p_two_sided=_two_sided_p(diff), **precision(diff, metric)))
    pvalues = [r["p_two_sided"] for r in rows]
    for row, adjusted in zip(rows, holm_adjust(pvalues)):
        row.update(holm_p=float(adjusted), holm_reject_005=bool(adjusted < .05))
    return pd.DataFrame(rows)
