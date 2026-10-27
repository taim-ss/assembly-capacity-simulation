"""Pure-Python replica of the P3 v2 finite assembly-flow model.

SYNTHETIC educational replica. Reproduces the AnyLogic .alp logic read directly from the
embedded Java source in ``portfolio/p3-assembly-flow/model/P3_Assembly_Flow.alp`` (v1, read-only)
plus the new v2 behaviour described in ``docs/v2-feature-spec.md``. With every v2 parameter at
its default, this engine must reproduce v1 native per-job release/finish/lead times to 1e-9 h
(verified in tests/ and in verify_against_native.py).

Tie policy: replica events use (time, insertion_sequence). Resource queues are FCFS.
Native internal simultaneous-event ordering is not inferred from the XML setting:
agreement is established only for the actual seed/configuration tapes compared in
the saved verification results. Corner-case ties outside those cases remain unverified.
"""
from __future__ import annotations

import heapq
import itertools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from java_random import JavaRandom
from quantiles import empirical_quantile, lognormal_from_u, weibull_from_u

STAGE_NAMES = ("Kitting", "Assembly", "Test", "Quality", "Handover")
_SAMPLES_PATH = Path(__file__).with_name("samples.json")


def load_samples() -> list[list[float]]:
    with open(_SAMPLES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class ScenarioConfig:
    rep_seed: int
    scenario_index: int  # 0 baseline, 1..5 = +1 at Kitting/Assembly/Test/Quality/Handover
    scenario_orders: int = 600
    mean_interarrival: float = 30.0
    service_scale: float = 1.0
    joint_bootstrap: bool = True
    rework_probability: float = 0.0
    cap_kitting: int = 1
    cap_assembly: int = 1
    cap_test: int = 1
    cap_quality: int = 1
    cap_handover: int = 1
    input_mode: int = 0
    component_mode: int = 0
    component_mean_interarrival: float = 5.0
    max_rework: int = 5

    def __post_init__(self):
        if not (0<=self.scenario_index<=5 and self.rep_seed>=0 and 1<=self.scenario_orders<=10000):
            raise ValueError("Invalid seed, scenario or order count")
        if any(not math.isfinite(x) or x<=0 for x in (self.mean_interarrival,self.service_scale,self.component_mean_interarrival)):
            raise ValueError("Times/scales must be finite and positive")
        if not 0<=self.rework_probability<=0.5 or not 0<=self.max_rework<=10:
            raise ValueError("Invalid rework settings")
        if self.input_mode not in (0,1) or self.component_mode not in (0,1):raise ValueError("Invalid input/component mode")
        if min(self.cap_kitting,self.cap_assembly,self.cap_test,self.cap_quality,self.cap_handover)<1:raise ValueError("Capacities must be positive")

    def capacities(self) -> tuple[int, int, int, int, int]:
        bump = [0, 0, 0, 0, 0]
        if 1 <= self.scenario_index <= 5:
            bump[self.scenario_index - 1] = 1
        base = (self.cap_kitting, self.cap_assembly, self.cap_test, self.cap_quality, self.cap_handover)
        return tuple(b + c for b, c in zip(base, bump))  # type: ignore[return-value]


@dataclass
class Job:
    job_id: int
    release_time: float
    row_index: int
    quality_draw: float
    draws: list[float]
    base_duration: list[float]  # 5 base (visit-0) durations, before rework-visit overrides
    entered_at: list[float] = field(default_factory=lambda: [math.nan] * 5)
    started_at: list[float] = field(default_factory=lambda: [math.nan] * 5)
    finished_at: list[float] = field(default_factory=lambda: [math.nan] * 5)
    reworks: int = 0
    n_rework_target: int = 0
    rework_tape: list[float] = field(default_factory=list)
    kit_wait: float = 0.0


class _Stage:
    """FCFS multi-server resource: Queue + ResourcePool-backed Service, PML-style."""

    __slots__ = ("capacity", "busy", "waiting")

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.busy = 0
        self.waiting: list[tuple[int, Job, float, int]] = []  # (seq, job, duration, visit)


def _fitted_duration(stage_k: int, u: float, sorted_kitting: list[float], scale: float) -> float:
    if stage_k == 0:
        return empirical_quantile(u, sorted_kitting) * scale
    if stage_k == 1:
        return lognormal_from_u(u, 0.30435615867119564, 19.265424718138505) * scale
    if stage_k == 2:
        return weibull_from_u(u, 1.697260159664356, 19.912596407400642) * scale
    if stage_k == 3:
        return lognormal_from_u(u, 0.42675962852691607, 7.957160535215475) * scale
    return lognormal_from_u(u, 0.3613639262514972, 2.7824739447886313) * scale


def run_scenario(cfg: ScenarioConfig, samples: list[list[float]] | None = None) -> dict:
    """Runs one (repSeed, scenario) finite campaign; returns per-job records and log lines."""
    samples = samples or load_samples()
    n_samples = len(samples)
    sorted_kitting = sorted(row[1] for row in samples)

    arrival_rng = JavaRandom(11001 + cfg.rep_seed)
    row_rng = JavaRandom(12001 + cfg.rep_seed)
    quality_rng = JavaRandom(13001 + cfg.rep_seed)
    stage_rng = [JavaRandom(21001 + 1000 * k + cfg.rep_seed) for k in range(5)]
    rework_rng = JavaRandom(14001 + cfg.rep_seed)
    component_rng = JavaRandom(15001 + cfg.rep_seed)

    caps = cfg.capacities()
    stages = [_Stage(c) for c in caps]

    log_lines: list[str] = ["P3_META,SYNTHETIC"]
    log_lines.append(
        "P3_CONFIG,{},{},false,{},{},{},{},{},0.0,{},{},{},{},{},{},{},{},{}".format(
            cfg.rep_seed, cfg.scenario_index, cfg.scenario_orders, cfg.mean_interarrival,
            cfg.service_scale, str(cfg.joint_bootstrap).lower(), cfg.rework_probability,
            cfg.cap_kitting,cfg.cap_assembly,cfg.cap_test,cfg.cap_quality,cfg.cap_handover, cfg.input_mode, cfg.component_mode, cfg.component_mean_interarrival, cfg.max_rework,
        )
    )

    seq_counter = itertools.count()
    events: list[tuple[float, int, str, object]] = []

    def schedule(time_: float, kind: str, payload: object) -> None:
        heapq.heappush(events, (time_, next(seq_counter), kind, payload))

    # ---- release schedule: ALL per-job draws happen at release, in job order (CRN-safe) ----
    jobs: list[Job] = []
    component_arrivals: list[float] = []
    if cfg.component_mode == 1:
        t = 0.0
        for _ in range(cfg.scenario_orders):
            t += -math.log(1.0 - component_rng.next_double()) * cfg.component_mean_interarrival
            component_arrivals.append(t)

    t_release = 0.0
    orders_in = 0
    for job_id in range(cfg.scenario_orders):
        t_release += -math.log(1.0 - arrival_rng.next_double()) * cfg.mean_interarrival
        row = row_rng.next_int(n_samples)
        quality_draw = quality_rng.next_double()
        draws = [0.0] * 5
        base_duration = [0.0] * 5
        for k in range(5):
            u = stage_rng[k].next_double()
            draws[k] = u
            if cfg.input_mode == 1:
                base_duration[k] = _fitted_duration(k, u, sorted_kitting, cfg.service_scale)
            else:
                r = row if cfg.joint_bootstrap else min(n_samples - 1, int(u * n_samples))
                base_duration[k] = samples[r][k + 1] * cfg.service_scale
        rework_tape = [rework_rng.next_double() for _ in range(2 * cfg.max_rework)]
        p = cfg.rework_probability
        if p <= 0:
            n_target = 0
        else:
            u = max(quality_draw, 1e-300)
            n_target = min(cfg.max_rework, int(math.floor(math.log(u) / math.log(p))))
        job = Job(job_id, t_release, row, quality_draw, draws, base_duration,
                  n_rework_target=n_target, rework_tape=rework_tape)
        jobs.append(job)
        schedule(t_release,"release",job)
        if cfg.component_mode == 1:
            kit_ready = max(t_release, component_arrivals[job_id])
            job.kit_wait = max(0.0, component_arrivals[job_id] - t_release)
            schedule(kit_ready, "stage_arrive", (job, 0, 0))
        else:
            schedule(t_release, "stage_arrive", (job, 0, 0))

    orders_out = 0
    done_jobs: list[Job] = []

    def duration_for(job: Job, stage_k: int, visit: int) -> float:
        if stage_k not in (1, 2) or visit == 0:
            return job.base_duration[stage_k]
        # rework visit v=1..N: Assembly_v uses tape[2(v-1)], Test_v uses tape[2(v-1)+1]
        idx = 2 * (visit - 1) + (0 if stage_k == 1 else 1)
        u = job.rework_tape[idx]
        r = min(len(samples) - 1, int(u * len(samples)))
        return samples[r][stage_k + 1] * cfg.service_scale

    def stage_arrive(job: Job, stage_k: int, visit: int, time_: float) -> None:
        stage = stages[stage_k]
        job.entered_at[stage_k] = time_
        duration = duration_for(job, stage_k, visit)
        if stage.busy < stage.capacity:
            stage.busy += 1
            job.started_at[stage_k] = time_
            schedule(time_ + duration, "stage_depart", (job, stage_k, visit, duration))
        else:
            heapq.heappush(stage.waiting, (next(seq_counter), job, duration, visit))

    def stage_depart(job: Job, stage_k: int, visit: int, duration: float, time_: float) -> None:
        nonlocal orders_out
        stage = stages[stage_k]
        stage.busy -= 1
        job.finished_at[stage_k] = time_
        log_lines.append(
            f"P3_STAGE,{cfg.rep_seed},{cfg.scenario_index},{job.job_id},{stage_k},"
            f"{job.entered_at[stage_k]},{job.started_at[stage_k]},{time_},{duration},{visit}"
        )
        if stage.waiting:
            _, next_job, next_dur, next_visit = heapq.heappop(stage.waiting)
            stage.busy += 1
            next_job.started_at[stage_k] = time_
            schedule(time_ + next_dur, "stage_depart", (next_job, stage_k, next_visit, next_dur))

        if stage_k == 1:  # Assembly always hands off to Test at the SAME visit index
            schedule(time_, "stage_arrive", (job, 2, visit))
        elif stage_k == 2 and job.reworks < job.n_rework_target:
            job.reworks += 1
            schedule(time_, "stage_arrive", (job, 1, job.reworks))  # back to Assembly, next visit
        elif stage_k < 4:
            schedule(time_, "stage_arrive", (job, stage_k + 1, 0))
        else:
            orders_out += 1
            log_lines.append(
                f"P3_ORDER,{cfg.rep_seed},{cfg.scenario_index},{job.job_id},{job.release_time},"
                f"{time_},{time_ - job.release_time},{job.reworks}"
            )
            log_lines.append(f"P3_STATE,{time_},{orders_in},{orders_out},{orders_in-orders_out}")
            done_jobs.append(job)

    while events:
        time_, _, kind, payload = heapq.heappop(events)
        if kind=="release":
            job=payload
            orders_in+=1
            if job.job_id<5:
                log_lines.append(f"P3_CRN,{cfg.rep_seed},{cfg.scenario_index},{job.job_id},{job.row_index},["+", ".join(map(repr,job.draws))+f"],{job.quality_draw}")
            log_lines.append(f"P3_IN,{time_},{orders_in},{orders_out},{orders_in-orders_out}")
        elif kind == "stage_arrive":
            job, stage_k, visit = payload  # type: ignore[misc]
            if stage_k==0:
                log_lines.append(f"P3_KIT,{cfg.rep_seed},{cfg.scenario_index},{job.job_id},{job.release_time},{time_},{job.kit_wait}")
            stage_arrive(job, stage_k, visit, time_)
        else:
            job, stage_k, visit, duration = payload  # type: ignore[misc]
            stage_depart(job, stage_k, visit, duration, time_)

    # Final metric integrals are independently reconstructed from event timestamps.
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from native.intervals import station_integrals
    stage_records={}
    for line in log_lines:
        if line.startswith("P3_STAGE,"):
            v=line.split(",");stage_records[(int(v[3]),int(v[4]),int(v[9]))]=tuple(map(float,v[5:9]))
    horizon=max((j.finished_at[4] for j in done_jobs),default=0.0)
    areas=station_integrals(dict(stages=stage_records,done=(orders_in,orders_out,horizon,cfg.scenario_orders)),caps)
    for k,(busy_area,queue_area,idle,starved,idle_units) in enumerate(areas):
        log_lines.append(f"P3_METRIC,{cfg.rep_seed},{cfg.scenario_index},{k},{horizon},{busy_area},{queue_area},{idle},0,0,{starved},{idle_units}")
    log_lines.append(f"P3_DONE,{cfg.rep_seed},{cfg.scenario_index},{orders_in},{orders_out},"
                      f"{max((j.finished_at[4] for j in done_jobs), default=0.0)},{cfg.scenario_orders}")

    return {"jobs": done_jobs, "log_lines": log_lines, "capacities": caps}
