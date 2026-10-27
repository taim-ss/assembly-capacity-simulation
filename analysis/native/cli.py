"""CLI: validate and summarize actual AnyLogic P3 logs (v1 and v2 schema).

SYNTHETIC educational data. No simulator or fallback results: absent/incomplete native
evidence is an error.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .mm1 import assess_mm1, assess_mmc
from .parsing import parse_log, require
from .validation import validate_matrix, validate_replay_source, validate_settings
from .outputs import write_outputs

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results" / "native")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "native-analysis")
    parser.add_argument("--mode", choices=["finite", "replay", "mm1", "mmc"], default="finite")
    parser.add_argument("--seeds", default=None,
                        help="Comma-separated expected seeds (default finite/mm1/mmc 1..10; replay 1)")
    parser.add_argument("--target", type=int, default=None,
                        help="Default finite 600; replay 195; mm1/mmc 10000")
    parser.add_argument("--interarrival", type=float, default=30.,
                        help="Expected finite-mode mean interarrival hours (default 30)")
    parser.add_argument("--service-scale", type=float, default=1.,
                        help="Expected finite-mode service-time multiplier (default 1)")
    parser.add_argument("--capacities", default="1,1,1,1,1",
                        help="Comma-separated baseline capacity vector (Kitting,Assembly,Test,Quality,Handover)")
    parser.add_argument("--rework", type=float, default=0.0, help="Expected reworkProbability")
    parser.add_argument("--input-mode", type=int, default=0, help="Expected inputMode")
    parser.add_argument("--component-mode", type=int, default=0, help="Expected componentMode")
    parser.add_argument("--component-mean", type=float, default=5.0,
                        help="Expected componentMeanInterarrival")
    parser.add_argument("--max-rework", type=int, default=5, help="Expected maxRework")
    parser.add_argument("--mmc-capacity", type=int, default=3, help="M/M/c server count")
    parser.add_argument("--mmc-lambda", type=float, default=2.1, help="M/M/c arrival rate")
    parser.add_argument("--mmc-mu", type=float, default=1.0, help="M/M/c per-server service rate")
    parser.add_argument("--calibration", type=Path,
                        default=ROOT / "analysis/calibration/clean_orders.csv",
                        help="Clean source CSV used to prove exact replay timestamps")
    parser.add_argument("--scenarios",default=None,help="Explicit expected scenario subset, e.g. 0,2,3")
    parser.add_argument("--warmup-jobs",type=int,default=0)
    args = parser.parse_args(argv)
    validate_settings(args.mode, args.interarrival, args.service_scale)
    seeds = ([int(x) for x in args.seeds.split(",")] if args.seeds
            else ([1] if args.mode == "replay" else list(range(1, 11))))
    require(len(seeds) == len(set(seeds)) and seeds and all(s >= 0 for s in seeds),
            "Invalid expected seeds")
    target = (args.target if args.target is not None
             else {"finite": 600, "replay": 195, "mm1": 10000, "mmc": 10000}[args.mode])
    require(target > 0, "Target must be positive")
    capacities = tuple(int(x) for x in args.capacities.split(","))
    require(len(capacities) == 5, "Capacities must have 5 entries")
    files = sorted(args.input.glob(f"native-seed-*-scenario-*-{args.mode}.log")) if args.input.is_dir() else []
    runs = [parse_log(path) for path in files]
    reps, stations, stages = validate_matrix(
        runs, seeds, args.mode, target, args.interarrival, args.service_scale,
        capacities, args.rework, args.input_mode, args.component_mode, args.component_mean,
        args.max_rework, args.mmc_capacity,
        [int(x) for x in args.scenarios.split(",")] if args.scenarios else None)
    replay_acceptance = (validate_replay_source(runs, args.calibration)
                        if args.mode == "replay" else None)
    mmc_params = dict(c=args.mmc_capacity, lam=args.mmc_lambda, mu=args.mmc_mu)
    write_outputs(runs, reps, stations, stages, args.output, args.mode, replay_acceptance,
                 mmc_params, args.warmup_jobs)
    print(f"SYNTHETIC: validated {len(runs)} actual native runs; outputs: {args.output.resolve()}")
    if args.mode == "mm1":
        print(f"MM1 benchmark acceptance: {assess_mm1(reps)['accepted']} (see mm1_verification.csv)")
    if args.mode == "mmc":
        acceptance = assess_mmc(reps, args.mmc_capacity, args.mmc_lambda, args.mmc_mu)
        print(f"MMC(c={args.mmc_capacity}) benchmark acceptance: {acceptance['accepted']} "
              f"(see mmc_verification.csv)")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(f"Native analysis rejected: {error}") from error
