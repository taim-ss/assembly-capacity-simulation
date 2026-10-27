"""Welch warm-up analysis for P3 native finite-campaign logs. SYNTHETIC educational data.

Reads the per-job release/finish records from actual AnyLogic P3_ORDER log lines, averages
lead time (and a live-WIP proxy) across replications by job index, smooths with a moving
window, and reports a visual warm-up estimate plus a quantified start-up bias.

Reusable for both v1 and v2 logs: only the first six P3_ORDER fields (tag, seed, scenario,
job, release, finish[, lead, reworks, ...]) are read; any additional trailing fields in a v2
log are ignored, so the same CLI works on either log family.

CLI:
    python welch.py --logs <dir> --out <dir> [--max-orders N] [--scenario S] [--window W]
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DEFAULT_WINDOW = 25
STABILITY_BAND = 0.05  # fraction of the steady-window mean


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class RunOrders:
    """One (seed, scenario) replication's per-job release/finish, ordered by job index."""

    seed: int
    scenario: int
    release: np.ndarray
    finish: np.ndarray


def parse_orders(path: Path) -> RunOrders:
    """Read only P3_CONFIG (for seed/scenario) and P3_ORDER (job, release, finish) lines."""
    seed = scenario = None
    jobs: dict[int, tuple[float, float]] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if line.startswith("P3_CONFIG,"):
            parts = line.split(",")
            require(len(parts) >= 3, f"{path.name}:{lineno}: malformed P3_CONFIG")
            seed, scenario = int(parts[1]), int(parts[2])
        elif line.startswith("P3_ORDER,"):
            parts = line.split(",")
            require(len(parts) >= 6, f"{path.name}:{lineno}: malformed P3_ORDER")
            job = int(parts[3])
            release, finish = float(parts[4]), float(parts[5])
            require(job not in jobs, f"{path.name}:{lineno}: duplicate job {job}")
            jobs[job] = (release, finish)
    require(seed is not None, f"{path.name}: no P3_CONFIG line found")
    require(jobs, f"{path.name}: no P3_ORDER lines found")
    n = max(jobs) + 1
    require(set(jobs) == set(range(n)), f"{path.name}: non-contiguous job indices")
    release = np.array([jobs[j][0] for j in range(n)], dtype=float)
    finish = np.array([jobs[j][1] for j in range(n)], dtype=float)
    return RunOrders(seed=seed, scenario=scenario, release=release, finish=finish)


def live_wip_proxy(run: RunOrders) -> np.ndarray:
    """WIP in system at the release instant of job j: #released - #finished so far, j in [0..n)."""
    n = len(run.release)
    wip = np.empty(n, dtype=float)
    for j in range(n):
        t = run.release[j]
        released = j + 1  # jobs 0..j have release <= t by construction (sorted release order)
        finished = int(np.sum(run.finish[: j + 1] <= t))
        wip[j] = released - finished
    return wip


def moving_average(values: np.ndarray, window: int) -> np.ndarray:
    require(window >= 1, "window must be >= 1")
    kernel = np.ones(window) / window
    padded = np.pad(values, (window - 1, 0), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def estimate_warmup(smoothed: np.ndarray, band: float = STABILITY_BAND) -> int:
    """Smallest job index after which the series stays within `band` of the late-window mean."""
    n = len(smoothed)
    tail_start = int(n * 0.8)
    steady_mean = float(np.mean(smoothed[tail_start:]))
    if steady_mean == 0:
        return 0
    deviation = np.abs(smoothed - steady_mean) / abs(steady_mean)
    within = deviation <= band
    # Find the smallest index W such that `within` holds for every index >= W.
    for candidate in range(n):
        if within[candidate:].all():
            return candidate
    return n - 1


def startup_bias(raw: np.ndarray, warmup: int) -> dict:
    n = len(raw)
    if warmup <= 0 or warmup >= n:
        return dict(warmup_jobs=warmup, startup_mean=None, steady_mean=float(np.mean(raw)),
                    absolute_bias_h=None, relative_bias_pct=None)
    startup_mean = float(np.mean(raw[:warmup]))
    steady_mean = float(np.mean(raw[warmup:]))
    bias = startup_mean - steady_mean
    relative = 100.0 * bias / steady_mean if steady_mean != 0 else None
    return dict(warmup_jobs=warmup, startup_mean=startup_mean, steady_mean=steady_mean,
                absolute_bias_h=bias, relative_bias_pct=relative)


def analyze(runs: list[RunOrders], window: int, max_orders: int | None) -> dict:
    require(runs, "No matching native logs found")
    lengths = {len(r.release) for r in runs}
    require(len(lengths) == 1, f"Replications have differing order counts: {sorted(lengths)}")
    n = next(iter(lengths))
    if max_orders is not None:
        n = min(n, max_orders)
    lead = np.vstack([r.finish[:n] - r.release[:n] for r in runs])
    wip = np.vstack([live_wip_proxy(r)[:n] for r in runs])
    mean_lead = lead.mean(axis=0)
    mean_wip = wip.mean(axis=0)
    smooth_lead = moving_average(mean_lead, window)
    smooth_wip = moving_average(mean_wip, window)
    warmup_lead = estimate_warmup(smooth_lead)
    warmup_wip = estimate_warmup(smooth_wip)
    warmup = max(warmup_lead, warmup_wip)
    return dict(
        n_jobs=n, n_replications=len(runs), window=window,
        warmup_estimate_lead_jobs=warmup_lead, warmup_estimate_wip_jobs=warmup_wip,
        warmup_estimate_jobs=warmup,
        lead_bias=startup_bias(mean_lead, warmup),
        wip_bias=startup_bias(mean_wip, warmup),
        job_index=np.arange(n), mean_lead=mean_lead, mean_wip=mean_wip,
        smooth_lead=smooth_lead, smooth_wip=smooth_wip,
    )


def write_outputs(result: dict, destination: Path, label: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(dict(
        job_index=result["job_index"], mean_lead_h=result["mean_lead"],
        smoothed_lead_h=result["smooth_lead"], mean_wip=result["mean_wip"],
        smoothed_wip=result["smooth_wip"],
    ))
    table.to_csv(destination / "welch_trajectory.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True, constrained_layout=True)
    axes[0].plot(result["job_index"], result["mean_lead"], color="lightgray", linewidth=.8,
                 label="replication-averaged (raw)")
    axes[0].plot(result["job_index"], result["smooth_lead"], color="C0",
                 label=f"moving average (window={result['window']})")
    axes[0].axvline(result["warmup_estimate_jobs"], color="red", linestyle="--",
                    label=f"warm-up estimate W={result['warmup_estimate_jobs']}")
    axes[0].set(ylabel="Lead time (h)", title=f"SYNTHETIC | Welch plot: {label}")
    axes[0].legend(fontsize=8)

    axes[1].plot(result["job_index"], result["mean_wip"], color="lightgray", linewidth=.8,
                 label="replication-averaged (raw)")
    axes[1].plot(result["job_index"], result["smooth_wip"], color="C1",
                 label=f"moving average (window={result['window']})")
    axes[1].axvline(result["warmup_estimate_jobs"], color="red", linestyle="--")
    axes[1].set(xlabel="Job index (release order)", ylabel="Live-WIP proxy (orders)")
    axes[1].legend(fontsize=8)
    fig.savefig(destination / "welch_plot.png", dpi=160)
    plt.close(fig)

    report = dict(
        label=label, n_replications=result["n_replications"], n_jobs=result["n_jobs"],
        window=result["window"],
        warmup_estimate_lead_jobs=result["warmup_estimate_lead_jobs"],
        warmup_estimate_wip_jobs=result["warmup_estimate_wip_jobs"],
        warmup_estimate_jobs=result["warmup_estimate_jobs"],
        lead_startup_bias=result["lead_bias"], wip_startup_bias=result["wip_bias"],
        method="Automated proxy for the visual Welch method: smallest job index after which "
               "the moving-average trajectory stays within 5% of the mean of the last 20% of "
               "jobs. This is a heuristic stand-in for eyeballing the plot, not a validated "
               "Welch procedure; `welch_plot.png` must be inspected by a human before the "
               "warm-up estimate is frozen in a run manifest.",
    )
    import json

    (destination / "welch_report.json").write_text(json.dumps(report, indent=2, allow_nan=False),
                                                     encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, required=True, help="Directory of native *.log files")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    parser.add_argument("--max-orders", type=int, default=None,
                        help="Truncate every replication to its first N job indices")
    parser.add_argument("--scenario", type=int, default=0,
                        help="Scenario to analyze (default 0 = baseline)")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                        help=f"Moving-average window in jobs (default {DEFAULT_WINDOW})")
    parser.add_argument("--pattern", default="native-seed-*-scenario-*-finite.log",
                        help="Glob pattern for log filenames")
    parser.add_argument("--label", default=None, help="Label for the plot title / report")
    args = parser.parse_args(argv)

    files = sorted(args.logs.glob(args.pattern)) if args.logs.is_dir() else []
    runs = [parse_orders(path) for path in files]
    runs = [r for r in runs if r.scenario == args.scenario]
    label = args.label or f"{args.logs.name} scenario {args.scenario}"
    result = analyze(runs, args.window, args.max_orders)
    write_outputs(result, args.out, label)
    bias = result["lead_bias"]
    print(f"SYNTHETIC: {result['n_replications']} replications, {result['n_jobs']} jobs analyzed")
    print(f"Warm-up estimate: {result['warmup_estimate_jobs']} jobs "
          f"(lead={result['warmup_estimate_lead_jobs']}, wip={result['warmup_estimate_wip_jobs']})")
    if bias["absolute_bias_h"] is not None:
        print(f"Start-up bias (mean lead, jobs 0..W vs steady window): "
              f"{bias['absolute_bias_h']:+.4f} h ({bias['relative_bias_pct']:+.2f}% of steady mean)")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(f"Welch analysis rejected: {error}") from error
