"""Regression check: v2-default native logs vs v1 native logs. SYNTHETIC educational data.

Per `docs/v2-preregistration.md` section 9: for every (seed, scenario) pair found in both
directories, per-job P3_ORDER (release, finish, lead) and per-stage P3_STAGE (entered, started,
finished, duration; visit must be 0) must match between the two directories to a max absolute
difference of 1e-9 hours. Any mismatch, or a (seed, scenario) present in one directory but not
the other, fails the whole regression and names the offending key.

CLI:
    python regress_vs_v1.py --v1 <dir> --v2 <dir> [--pattern GLOB] [--tolerance 1e-9]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from native.parsing import parse_log, require  # noqa: E402

DEFAULT_TOLERANCE = 1e-9


def _stage_records(run):
    """{(job, stage): (entered, started, finished, duration)} restricted to visit 0."""
    return {(job, stage): record for (job, stage, visit), record in run["stages"].items()
            if visit == 0}


def compare_run(v1_run, v2_run, tolerance):
    key = v1_run["key"]
    require(v2_run["key"] == key, f"Key mismatch: {v1_run['key']} vs {v2_run['key']}")
    mismatches = []
    v1_jobs, v2_jobs = set(v1_run["orders"]), set(v2_run["orders"])
    require(v1_jobs == v2_jobs, f"{key}: job-id sets differ "
            f"(v1-only={sorted(v1_jobs - v2_jobs)[:5]}, v2-only={sorted(v2_jobs - v1_jobs)[:5]})")
    max_order_diff = 0.0
    for job in sorted(v1_jobs):
        v1_release, v1_finish, v1_lead, _ = v1_run["orders"][job]
        v2_release, v2_finish, v2_lead, v2_reworks = v2_run["orders"][job]
        require(v2_reworks == 0, f"{key}/job{job}: v2-default run has nonzero reworks")
        diffs = [abs(v1_release - v2_release), abs(v1_finish - v2_finish), abs(v1_lead - v2_lead)]
        max_order_diff = max(max_order_diff, *diffs)
        if max(diffs) > tolerance:
            mismatches.append(dict(key=key, job=job, field="order", max_abs_diff_h=max(diffs)))
    v1_stages, v2_stages = _stage_records(v1_run), _stage_records(v2_run)
    require(set(v1_stages) == set(v2_stages), f"{key}: stage-record keys differ")
    max_stage_diff = 0.0
    for stage_key in sorted(v1_stages):
        v1_values, v2_values = v1_stages[stage_key], v2_stages[stage_key]
        diffs = [abs(a - b) for a, b in zip(v1_values, v2_values)]
        max_stage_diff = max(max_stage_diff, *diffs)
        if max(diffs) > tolerance:
            mismatches.append(dict(key=key, job=stage_key[0], stage=stage_key[1],
                                   field="stage", max_abs_diff_h=max(diffs)))
    return dict(key=key, max_order_diff_h=max_order_diff, max_stage_diff_h=max_stage_diff,
               n_mismatches=len(mismatches), mismatches=mismatches[:10])


def regress(v1_dir: Path, v2_dir: Path, pattern: str, tolerance: float):
    v1_files = {parse_log(p)["key"]: p for p in sorted(v1_dir.glob(pattern))}
    v2_files = {parse_log(p)["key"]: p for p in sorted(v2_dir.glob(pattern))}
    common = sorted(set(v1_files) & set(v2_files))
    require(common, f"No matching (seed, scenario) keys between {v1_dir} and {v2_dir}")
    only_v1 = sorted(set(v1_files) - set(v2_files))
    only_v2 = sorted(set(v2_files) - set(v1_files))
    results = []
    worst = 0.0
    for key in common:
        v1_run, v2_run = parse_log(v1_files[key]), parse_log(v2_files[key])
        result = compare_run(v1_run, v2_run, tolerance)
        results.append(result)
        worst = max(worst, result["max_order_diff_h"], result["max_stage_diff_h"])
    failed = [r for r in results if r["n_mismatches"] > 0]
    return dict(tolerance_h=tolerance, compared_keys=len(common), only_in_v1=only_v1,
               only_in_v2=only_v2, worst_max_abs_diff_h=worst, failed_keys=len(failed),
               passed=bool(not failed and not only_v1 and not only_v2), details=results)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1", type=Path, required=True, help="Directory of v1 native logs")
    parser.add_argument("--v2", type=Path, required=True, help="Directory of v2-default native logs")
    parser.add_argument("--pattern", default="native-seed-*-scenario-*-finite.log")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    args = parser.parse_args(argv)
    report = regress(args.v1, args.v2, args.pattern, args.tolerance)
    import json
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))
    if not report["passed"]:
        for row in report["details"]:
            if row["n_mismatches"]:
                print(f"MISMATCH {row['key']}: {row['n_mismatches']} fields over tolerance "
                      f"(max order diff {row['max_order_diff_h']:.3e} h, "
                      f"max stage diff {row['max_stage_diff_h']:.3e} h)")
        raise SystemExit("Regression FAILED: v2 defaults do not reproduce v1 within tolerance")
    print(f"Regression PASSED: {report['compared_keys']} (seed, scenario) pairs match within "
          f"{args.tolerance:.0e} h (worst observed diff {report['worst_max_abs_diff_h']:.3e} h)")


if __name__ == "__main__":
    main()
