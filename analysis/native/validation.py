"""Validate parsed P3 native runs against the v2 feature spec. SYNTHETIC educational data.

Generalizes v1's hard-coded capacity-1-plus-one-at-a-time assumption to an arbitrary baseline
capacity vector (needed for E2's [2,5,5,3,1] and E4/E5's custom vectors), and adds rework-visit
and kitting-with-Combine structural checks. Backward compatible: a v1 log (capacities
[1,1,1,1,1], rework=0, no P3_KIT lines) validates exactly as it did under v1's analyzer.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd

from .parsing import STAGES, SCENARIOS, close, integer, number, require


def validate_settings(mode, interarrival, service_scale):
    require(math.isfinite(interarrival) and interarrival > 0
            and math.isfinite(service_scale) and service_scale > 0,
            "Expected interarrival and service scale must be finite and positive")
    require(mode in ("finite", "replay", "mm1", "mmc"), f"Unknown mode: {mode}")
    require(mode == "finite" or (interarrival == 30 and service_scale == 1)
            or mode == "mmc",
            "Custom sensitivity settings require finite mode")


def scenario_capacities(baseline, scenario):
    """Scenario 0 = baseline vector; scenario k in 1..5 adds one unit at stage k-1."""
    require(len(baseline) == 5, "Baseline capacity vector must have 5 entries")
    require(0 <= scenario <= 5, "Invalid scenario")
    capacities = list(baseline)
    if scenario:
        capacities[scenario - 1] += 1
    return tuple(capacities)


def validate_run(run, mode="finite", target=600, interarrival=30., service_scale=1.,
                 baseline_capacities=(1, 1, 1, 1, 1), rework=0.0, input_mode=0,
                 component_mode=0, component_mean=5.0, max_rework=5, mmc_capacity=1):
    validate_settings(mode, interarrival, service_scale)
    seed, scenario = run["key"]
    require(run["meta"] and run["config"] is not None, "Missing synthetic/config metadata")
    require(run["done"] is not None, "Truncated run: missing P3_DONE")
    c = run["config"]
    require(0 <= scenario <= 5 and seed >= 0, "Invalid seed/scenario")
    require(c["replay"] == (mode == "replay") and c["target"] == target,
            "Mode/target config mismatch")
    require(run["verification"] == ({"mm1": "mm1", "mmc": "mmc"}.get(mode)),
            "Verification mode mismatch")
    if mode=="mm1":
        require(run.get("verification_parameters")=={"lambda":"0.5","mu":"1.0"},"Invalid verification mode parameters")
        for job,tape in run["crn"].items():
            duration=run["stages"].get((job,0,0),(0,0,0,float('nan')))[3]
            require(close(duration,-math.log(1-tape[1])),"Invalid exponential service tape")
    if mode=="mmc":
        pars=run.get("verification_parameters",{})
        require(set(pars)=={"lambda","mu"} and close(float(pars["lambda"]),2.1) and close(float(pars["mu"]),1.0),"Invalid verification mode parameters")
        for job,tape in run["crn"].items():
            require(close(run["stages"][(job,0,0)][3],-math.log(1-tape[1])),"Invalid exponential service tape")
    expected_interarrival = 2 if mode == "mm1" else interarrival
    require(close(c["interarrival"], expected_interarrival) and close(c["scale"], service_scale)
            and c["joint"] and close(c["rework"], rework) and c["warmup"] == 0,
            "Unsupported/config mismatch")
    if mode in ("mm1", "mmc"):
        expected_caps = (mmc_capacity, 1, 1, 1, 1) if mode == "mmc" else (1, 1, 1, 1, 1)
    else:
        expected_caps = scenario_capacities(baseline_capacities, scenario)
    require(tuple(c[f"cap_{s}"] for s in STAGES) == tuple(baseline_capacities if mode not in ("mm1","mmc") else expected_caps),
            f"Capacity mismatch: expected {expected_caps}, got "
            f"{tuple(c[f'cap_{s}'] for s in STAGES)}")
    if c["schema"] == "v2":
        require(c["inputMode"] == input_mode and c["componentMode"] == component_mode
                and (component_mode == 0 or close(c["componentMeanInterarrival"], component_mean))
                and c["maxRework"] == max_rework, "v2 input/component/rework setting mismatch")
    arrived, departed, horizon, done_target = run["done"]
    require(horizon > 0 and arrived == departed == done_target == target,
            "Run did not fully drain its configured target")
    require(set(run["orders"]) == set(range(target)), "Missing/non-target job IDs")
    from .conservation import validate_transitions
    validate_transitions(run,target)
    require(set(run["crn"]) == set(range(min(target, 5))), "Missing first-five CRN job tapes")

    leads = []
    for job, (release, finish, lead, reworks) in run["orders"].items():
        require(0 <= release <= finish <= horizon + 1e-7 and lead >= 0
                and close(lead, finish - release)
                and 0 <= reworks <= max_rework
                and (reworks == 0 if rework <= 0 else True),
                f"Invalid lead/rework for job {job}")
        leads.append(lead)
    require(close(max(v[1] for v in run["orders"].values()), horizon),
            "Terminal time differs from last completion")

    visits_by_job_stage = {}
    require(all(len(key)==3 for key in run["stages"]), "Invalid stage times / record key")
    for job, stage, visit in run["stages"]:
        visits_by_job_stage.setdefault((job, stage), set()).add(visit)
    run["visits_index"] = visits_by_job_stage
    require(all(0<=s<=4 and v>=0 for j,s,v in run["stages"]),"Invalid stage visit key")
    stage_rows = []
    for stage, name in enumerate(STAGES):
        reworkable = stage in (1, 2) and rework > 0
        durations, waits = [], []
        for job in range(target):
            reworks_j = run["orders"][job][3]
            expected_visits = (set(range(reworks_j + 1)) if reworkable else {0})
            observed_visits = visits_by_job_stage.get((job, stage), set())
            require(observed_visits == expected_visits,
                    f"Visit mismatch job {job} stage {name}: expected {expected_visits}, "
                    f"got {observed_visits}")
            for visit in sorted(expected_visits):
                entered, started, finished, duration = run["stages"][(job, stage, visit)]
                require(0 <= entered <= started <= finished <= horizon + 1e-7
                        and (duration >= 0 if mode in ("mm1", "mmc") else duration > 0)
                        and close(finished - started, duration),
                        f"Invalid stage times {job}/{name}/visit{visit}")
                if mode in ("mm1", "mmc"):
                    require((duration > 0 if stage == 0 else duration == 0),
                            f"{mode.upper()} requires positive service only at stage zero")
                expected_entry = _expected_entry(run, job, stage, visit, name)
                require(close(entered, expected_entry),
                        f"Broken stage chain {job}/{name}/visit{visit}")
                durations.append(duration)
                waits.append(started - entered)
                if stage == 4 and visit == 0:
                    require(close(finished, run["orders"][job][1]),
                            "Order/stage completion mismatch")
        stage_rows.append(dict(seed=seed, scenario=scenario, stage=name,
                               mean_service_h=float(np.mean(durations)) if durations else float("nan"),
                               p90_service_h=float(np.quantile(durations, .9)) if durations else float("nan"),
                               mean_wait_h=float(np.mean(waits)) if waits else float("nan")))

    if c["schema"]=="v2" and mode=="finite":
        _validate_kits(run, target, horizon)

    station_rows = []
    exact_areas=None
    if c["schema"]=="v2" and mode!="replay":
        from .intervals import station_integrals
        exact_areas=station_integrals(run,expected_caps)
    for stage, name in enumerate(STAGES):
        history = [x for x in run["metrics"] if x[0] == stage]
        require(history, f"Missing station metrics {name}")
        capacity = expected_caps[stage]
        prior = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        for st, t, busy_area, queue_area, idle, busy, queued, starved, idle_units in history:
            require(t >= prior[0] and t <= horizon + 1e-7
                    and all(x >= y - 1e-7 for x, y in zip(
                        [busy_area, queue_area, idle, starved, idle_units], prior[1:]))
                    and 0 <= busy <= capacity and queued >= 0 and idle <= t + 1e-7
                    and busy_area <= capacity * t + 1e-7, "Invalid metric integral/state")
            prior = [t, busy_area, queue_area, idle, starved, idle_units]
        st, t, busy_area, queue_area, idle, busy, queued, starved, idle_units = history[-1]
        require(close(t, horizon) and busy == queued == 0, f"Station not drained: {name}")
        if exact_areas is not None:
            require(all(close(a,b) for a,b in zip([busy_area,queue_area,idle,starved,idle_units],exact_areas[stage])), "Metric evidence differs from exact stage-state integrals")
        if mode != "replay":
            service = sum(run["stages"][(j, stage, v)][3]
                          for j in range(target)
                          for v in visits_by_job_stage.get((j, stage), set()))
            wait = sum(run["stages"][(j, stage, v)][1] - run["stages"][(j, stage, v)][0]
                      for j in range(target)
                      for v in visits_by_job_stage.get((j,stage),set()))
            require(close(busy_area, service) and close(queue_area, wait),
                    "Station integrals disagree with job timestamps")
            station_rows.append(dict(seed=seed, scenario=scenario, stage=name, capacity=capacity,
                                     utilization=busy_area / (capacity * horizon),
                                     mean_queue=queue_area / horizon,
                                     empty_station_idle_fraction=idle / horizon,
                                     starved_by_upstream_fraction=starved / horizon,
                                     idle_units_mean=idle_units / horizon))
    row = dict(seed=seed, scenario=scenario, scenario_name=SCENARIOS[scenario],
               target=target, final_time_h=horizon, mean_lead_h=float(np.mean(leads)),
               p90_lead_h=float(np.quantile(leads, .9)), mean_wip=sum(leads) / horizon,
               throughput_per_h=target / horizon)
    if mode in ("mm1", "mmc"):
        require(scenario == 0, f"{mode.upper()} requires baseline capacity")
        require(all(run["orders"][j][0] > (run["orders"][j-1][0] if j else 0)
                    for j in range(target)), f"{mode.upper()} arrivals must be strictly increasing")
        row.update(mean_wait_h=stage_rows[0]["mean_wait_h"],
                   mean_queue=station_rows[0]["mean_queue"], utilization=station_rows[0]["utilization"])
    return row, station_rows, stage_rows


def _expected_entry(run, job, stage, visit, name):
    """Entry time for a (job, stage, visit): previous visit of the rework pair, or the chain."""
    if stage==2:  # Every Test visit follows the SAME Assembly visit.
        return run["stages"][(job,1,visit)][2]
    if visit > 0:
        if name == "Assembly":  # Assembly visit v follows Test visit v-1
            return run["stages"][(job, 2, visit - 1)][2]
        if name == "Test":  # Test visit v follows Assembly visit v (same v)
            return run["stages"][(job, 1, visit)][2]
        raise ValueError(f"Unexpected reworked stage with visit>0: {name}")
    if stage == 0:
        return run["kits"][job][1] if job in run["kits"] else run["orders"][job][0]
    prior_stage = stage - 1
    prior_visits = run["visits_index"].get((job, prior_stage), set())
    return run["stages"][(job, prior_stage, max(prior_visits))][2]


def _validate_kits(run, target, horizon):
    require(set(run["kits"]) == set(range(target)), "Missing/non-target kit records")
    prior_ready = -1.0
    for job in range(target):
        release, ready, wait = run["kits"][job]
        order_release = run["orders"][job][0]
        require(close(release, order_release), f"Kit release mismatch job {job}")
        require(ready >= release - 1e-7 and ready <= horizon + 1e-7 and wait >= -1e-7
                and close(wait, max(0.0, ready - release), abs_tol=1e-6),
                f"Invalid kit wait job {job}")
        require(ready >= prior_ready - 1e-6, f"Kit readiness not FIFO-monotonic at job {job}")
        prior_ready = ready


def validate_matrix(runs, seeds, mode="finite", target=600, interarrival=30., service_scale=1.,
                    baseline_capacities=(1, 1, 1, 1, 1), rework=0.0, input_mode=0,
                    component_mode=0, component_mean=5.0, max_rework=5, mmc_capacity=1, scenarios=None):
    validate_settings(mode, interarrival, service_scale)
    require(runs, "No native logs found. Run AnyLogic first; no output was generated.")
    expected_scenarios=list(scenarios) if scenarios is not None else (list(range(6)) if mode=="finite" else [0])
    expected = {(s,k) for s in seeds for k in expected_scenarios}
    keys = [r["key"] for r in runs]
    require(len(keys) == len(set(keys)), "Duplicate seed/scenario run")
    require(set(keys) == expected,
            f"Seed/scenario matrix mismatch; missing={sorted(expected-set(keys))}; "
            f"unexpected={sorted(set(keys)-expected)}")
    replications, stations, stages = [], [], []
    for run in runs:
        row, station, stage = validate_run(run, mode, target, interarrival, service_scale,
                                           baseline_capacities, rework, input_mode,
                                           component_mode, component_mean, max_rework,
                                           mmc_capacity)
        replications.append(row)
        stations.extend(station)
        stages.extend(stage)
    by_key = {r["key"]: r for r in runs}
    if mode == "finite":
        for seed in seeds:
            base = by_key.get((seed, 0))
            if base is None:
                continue
            for scenario in range(1, 6):
                other = by_key.get((seed, scenario))
                if other is None:
                    continue
                require(base["crn"] == other["crn"], f"CRN tape mismatch {seed}/{scenario}")
                for job in range(target):
                    require(close(base["orders"][job][0], other["orders"][job][0]),
                            f"CRN release mismatch {seed}/{scenario}/{job}")
                    require(close(base["stages"][(job, 0, 0)][3], other["stages"][(job, 0, 0)][3]),
                            f"CRN service mismatch {seed}/{scenario}/{job}")
    return pd.DataFrame(replications), pd.DataFrame(stations), pd.DataFrame(stages)


def validate_replay_source(runs, source):
    """Prove every replay timestamp against the same ordered clean calibration rows."""
    columns = ["release_h", "kitting_h", "assembly_h", "test_h", "quality_h", "handover_h"]
    frame = pd.read_csv(source, encoding="utf-8-sig")
    require(set(["order_id", *columns]).issubset(frame.columns), "Invalid replay source schema")
    require(frame.order_id.notna().all() and frame.order_id.is_unique, "Invalid replay source IDs")
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    require(np.isfinite(frame[columns].to_numpy()).all()
            and (frame[columns] >= 0).all().all(), "Invalid replay source timestamps")
    samples = frame.sort_values(["release_h", "order_id"])[columns].to_numpy()
    maximum_error = 0.0
    for run in runs:
        require(run["config"]["replay"] and len(samples) == len(run["orders"]),
                "Replay source row count/mode mismatch")
        for job, sample in enumerate(samples):
            release, *durations = sample
            expected_finish = release + sum(durations)
            observed = list(run["orders"][job][:3])
            expected = [release, expected_finish, sum(durations)]
            entered = release
            for stage, duration in enumerate(durations):
                observed.extend(run["stages"][(job, stage, 0)])
                expected.extend([entered, entered, entered + duration, duration])
                entered += duration
            error = max(abs(float(a) - float(b)) for a, b in zip(observed, expected))
            require(error <= 1e-6, f"Replay source timestamp mismatch: job {job}; error={error} h")
            maximum_error = max(maximum_error, error)
    return dict(path=str(source.resolve()), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                clean_orders=len(samples), timestamp_tolerance_h=1e-6,
                maximum_absolute_error_h=maximum_error)
