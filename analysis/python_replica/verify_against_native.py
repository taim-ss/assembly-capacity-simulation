"""Verifies the Python replica against v1 native AnyLogic logs (read-only reference).

Compares P3_STAGE (entered/started/finished/duration) and P3_ORDER (release/finish/lead)
numeric fields, parsed as floats, for a chosen set of (seed, scenario) native log files found
under the read-only v1 results directory. Prints the maximum absolute difference found and any
structural mismatches (missing jobs, extra jobs, mismatched stage counts).

Usage: python verify_against_native.py <native_log_dir> [--seeds 11-20] [--scenarios 0-5]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from model import ScenarioConfig, run_scenario

_STAGE_RE = re.compile(r"^P3_STAGE,(\d+),(\d+),(\d+),(\d+),([^,]+),([^,]+),([^,]+),([^,]+)")
_ORDER_RE = re.compile(r"^P3_ORDER,(\d+),(\d+),(\d+),([^,]+),([^,]+),([^,]+),(\d+)")
_CONFIG_RE = re.compile(
    r"^P3_CONFIG,(\d+),(\d+),(\w+),(\d+),([^,]+),([^,]+),(\w+),([^,]+),([^,]+),(\d+),(\d+),(\d+),(\d+),(\d+)"
)


def parse_native_log(path: Path) -> dict:
    stages: dict[tuple[int, int], tuple[float, float, float, float]] = {}
    orders: dict[int, tuple[float, float, float, int]] = {}
    config = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _CONFIG_RE.match(line)
        if m:
            config = m
            continue
        m = _STAGE_RE.match(line)
        if m:
            job_id, stage = int(m.group(3)), int(m.group(4))
            entered, started, finished, duration = (float(m.group(i)) for i in (5, 6, 7, 8))
            # native logs may contain multiple visits per stage (rework); keep the LAST one seen
            # to mirror the replica's job.finished_at semantics, but for v1 defaults there is
            # exactly one line per (job, stage) so this is a no-op.
            stages[(job_id, stage)] = (entered, started, finished, duration)
            continue
        m = _ORDER_RE.match(line)
        if m:
            job_id = int(m.group(3))
            release, finish, lead = (float(m.group(i)) for i in (4, 5, 6))
            reworks = int(m.group(7))
            orders[job_id] = (release, finish, lead, reworks)
    return {"stages": stages, "orders": orders, "config": config}


def run_and_compare(native_path: Path) -> dict:
    native = parse_native_log(native_path)
    cfg_m = native["config"]
    assert cfg_m is not None, f"no P3_CONFIG line in {native_path}"
    rep_seed = int(cfg_m.group(1))
    scenario = int(cfg_m.group(2))
    scenario_orders = int(cfg_m.group(4))
    mean_interarrival = float(cfg_m.group(5))
    service_scale = float(cfg_m.group(6))
    joint = cfg_m.group(7) == "true"
    rework_p = float(cfg_m.group(8))
    cap_k, cap_a, cap_t, cap_q, cap_h = (int(cfg_m.group(i)) for i in (10, 11, 12, 13, 14))

    cfg = ScenarioConfig(
        rep_seed=rep_seed, scenario_index=scenario, scenario_orders=scenario_orders,
        mean_interarrival=mean_interarrival, service_scale=service_scale,
        joint_bootstrap=joint, rework_probability=rework_p,
        cap_kitting=cap_k, cap_assembly=cap_a, cap_test=cap_t, cap_quality=cap_q, cap_handover=cap_h,
    )
    result = run_scenario(cfg)

    max_abs_diff = 0.0
    mismatches: list[str] = []
    replica_stage_lines = [ln for ln in result["log_lines"] if ln.startswith("P3_STAGE,")]
    replica_stages: dict[tuple[int, int], tuple[float, float, float, float]] = {}
    for ln in replica_stage_lines:
        m = _STAGE_RE.match(ln)
        job_id, stage = int(m.group(3)), int(m.group(4))
        entered, started, finished, duration = (float(m.group(i)) for i in (5, 6, 7, 8))
        replica_stages[(job_id, stage)] = (entered, started, finished, duration)

    if set(replica_stages) != set(native["stages"]):
        missing = set(native["stages"]) - set(replica_stages)
        extra = set(replica_stages) - set(native["stages"])
        mismatches.append(f"stage key mismatch: missing={len(missing)} extra={len(extra)}")

    for key in set(replica_stages) & set(native["stages"]):
        for a, b in zip(replica_stages[key], native["stages"][key]):
            max_abs_diff = max(max_abs_diff, abs(a - b))

    replica_orders: dict[int, tuple[float, float, float, int]] = {}
    for ln in result["log_lines"]:
        if ln.startswith("P3_ORDER,"):
            m = _ORDER_RE.match(ln)
            job_id = int(m.group(3))
            release, finish, lead = (float(m.group(i)) for i in (4, 5, 6))
            replica_orders[job_id] = (release, finish, lead, int(m.group(7)))

    if set(replica_orders) != set(native["orders"]):
        mismatches.append("order key mismatch")
    for key in set(replica_orders) & set(native["orders"]):
        ra = replica_orders[key]
        nb = native["orders"][key]
        for a, b in zip(ra[:3], nb[:3]):
            max_abs_diff = max(max_abs_diff, abs(a - b))
        if ra[3] != nb[3]:
            mismatches.append(f"job {key} rework count mismatch: replica={ra[3]} native={nb[3]}")

    return {
        "path": str(native_path), "max_abs_diff": max_abs_diff, "mismatches": mismatches,
        "n_jobs_native": len(native["orders"]), "n_jobs_replica": len(replica_orders),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("native_log_dir")
    ap.add_argument("--glob", default="*.log")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--seeds",default="11-20")
    args = ap.parse_args()
    overall_max = 0.0
    any_mismatch = False
    results = []
    lo,hi=map(int,args.seeds.split("-"))
    for path in sorted(Path(args.native_log_dir).glob(args.glob)):
        seed=int(re.search(r"native-seed-(\d+)",path.name)[1])
        if not lo<=seed<=hi:continue
        r = run_and_compare(path)
        results.append(r)
        overall_max = max(overall_max, r["max_abs_diff"])
        if r["mismatches"]:
            any_mismatch = True
        print(f"{path.name:55s} jobs(native/replica)={r['n_jobs_native']:4d}/{r['n_jobs_replica']:4d}"
              f"  max_abs_diff={r['max_abs_diff']:.3e}  mismatches={r['mismatches']}")
    print()
    report=dict(label="SYNTHETIC independent Python replica versus actual native logs",files=len(results),maximum_absolute_error_h=overall_max,passed=bool(results and not any_mismatch and overall_max<=1e-9),details=results)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2),encoding="utf8")
    print(f"TOTAL FILES: {len(results)}  OVERALL MAX ABS DIFF: {overall_max:.3e}  ANY MISMATCH: {any_mismatch}")

    if not report["passed"]:raise SystemExit("Replica/native agreement FAILED")


if __name__ == "__main__":
    main()
