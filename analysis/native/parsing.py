"""Parse actual AnyLogic P3 native log files (v1 and v2 schema). SYNTHETIC educational data.

No simulator or fallback results: absent/incomplete native evidence is an error. Backward
compatible with v1 logs â€” a v2 trailing field absent from an older log line gets its v1
default, never a silent guess at a different value.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

STAGES = ["Kitting", "Assembly", "Test", "Quality", "Handover"]
SCENARIOS = ["Baseline", *[f"{stage} +1" for stage in STAGES]]
METRICS = ["mean_lead_h", "p90_lead_h", "mean_wip", "throughput_per_h"]
LABEL = "SYNTHETIC - actual AnyLogic native output; educational assumptions"

CONFIG_KEYS_V1 = ["seed", "scenario", "replay", "target", "interarrival", "scale",
                  "joint", "rework", "warmup", *[f"cap_{s}" for s in STAGES]]
CONFIG_KEYS_V2_EXTRA = ["inputMode", "componentMode", "componentMeanInterarrival", "maxRework"]
CONFIG_KEYS = CONFIG_KEYS_V1 + CONFIG_KEYS_V2_EXTRA
CONFIG_V2_DEFAULTS = {"inputMode": 0, "componentMode": 0,
                      "componentMeanInterarrival": 5.0, "maxRework": 5}

MM1_TARGETS = {"mean_lead_h": 2.0, "mean_wait_h": 1.0, "mean_wip": 1.0,
               "mean_queue": .5, "throughput_per_h": .5, "utilization": .5}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    result = float(value)
    require(math.isfinite(result), f"Non-finite value: {value}")
    return result


def integer(value):
    result = number(value)
    require(result.is_integer(), f"Expected integer: {value}")
    return int(result)


def flag(value):
    require(value in {"true", "false"}, f"Invalid boolean: {value}")
    return value == "true"


def close(a, b, rel_tol=1e-8, abs_tol=1e-7):
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


def _parse_config(values):
    require(len(values) in (len(CONFIG_KEYS_V1), len(CONFIG_KEYS)), "Invalid config schema")
    is_v2 = len(values) == len(CONFIG_KEYS)
    keys = CONFIG_KEYS if is_v2 else CONFIG_KEYS_V1
    config = dict(zip(keys, values))
    for field in ["seed", "scenario", "target", *[f"cap_{s}" for s in STAGES]]:
        config[field] = integer(config[field])
    for field in ["replay", "joint"]:
        config[field] = flag(config[field])
    for field in ["interarrival", "scale", "rework", "warmup"]:
        config[field] = number(config[field])
    if is_v2:
        config["inputMode"] = integer(config["inputMode"])
        config["componentMode"] = integer(config["componentMode"])
        config["componentMeanInterarrival"] = number(config["componentMeanInterarrival"])
        config["maxRework"] = integer(config["maxRework"])
    else:
        config.update(CONFIG_V2_DEFAULTS)
    config["schema"] = "v2" if is_v2 else "v1"
    return config


def _parse_stage(values):
    """v1: 8 values (seed,scenario,job,stage,entered,started,finished,duration); v2 adds visit."""
    require(len(values) in (8, 9), "Invalid stage schema")
    seed, scenario, job, stage = (integer(values[0]), integer(values[1]),
                                  integer(values[2]), integer(values[3]))
    entered, started, finished, duration = map(number, values[4:8])
    visit = integer(values[8]) if len(values) == 9 else 0
    return (seed, scenario), job, stage, visit, (entered, started, finished, duration)


def _parse_metric(values):
    """v1: 9 values; v2 adds starvedByUpstream, idleUnits (11 total)."""
    require(len(values) in (9, 11), "Invalid station metric schema")
    stage = integer(values[2])
    t, busy_area, queue_area, idle = map(number, values[3:7])
    busy, queued = integer(values[7]), integer(values[8])
    starved = number(values[9]) if len(values) == 11 else 0.0
    idle_units = number(values[10]) if len(values) == 11 else 0.0
    return stage, t, busy_area, queue_area, idle, busy, queued, starved, idle_units


def _parse_kit(values):
    """P3_KIT,seed,scenario,job,orderReleaseTime,kitReadyTime,kitWait (finite, componentMode=1)."""
    require(len(values) == 6, "Invalid kit schema")
    job = integer(values[2])
    release, ready, wait = map(number, values[3:6])
    return job, (release, ready, wait)


def parse_log(path: Path):
    """Read one completed run; arrays in P3_CRN deliberately are not CSV quoted."""
    run = {"path": str(path.resolve()), "orders": {}, "metrics": [], "crn": {},
           "stages": {}, "kits": {}, "config": None, "done": None, "meta": False,
           "verification": None,"transitions":[]}
    key = None
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line.startswith("P3_"):
            continue
        parts = line.split(",")
        tag, values = parts[0], parts[1:]
        try:
            require(run["done"] is None, "Records follow terminal P3_DONE")
            if tag == "P3_META":
                require(values == ["SYNTHETIC"] and not run["meta"], "Bad/duplicate metadata")
                run["meta"] = True
                continue
            if tag == "P3_VERIFICATION_MODE":
                require(values[:1] in ([ "MM1"], ["MMC"]) and run["verification"] is None,
                        "Invalid/duplicate verification mode")
                run["verification_parameters"] = dict(x.split("=",1) for x in values[1:])
                run["verification"] = "mm1" if values[0] == "MM1" else "mmc"
                continue
            if tag in {"P3_IN", "P3_STATE"}:
                require(len(values) == 4, "Invalid conservation record")
                t, arrived, departed, wip = map(number, values)
                require(t >= 0 and all(x.is_integer() for x in [arrived, departed, wip])
                        and arrived >= departed >= 0 and arrived - departed == wip,
                        "Conservation failure")
                run['transitions'].append((tag,t,int(arrived),int(departed),int(wip)))
                continue
            require(len(values) >= 2, "Missing seed/scenario")
            observed_key = (integer(values[0]), integer(values[1]))
            key = observed_key if key is None else key
            require(key == observed_key, "Mixed seed/scenario within file")
            if tag == "P3_CONFIG":
                require(run["config"] is None, "Duplicate config")
                run["config"] = _parse_config(values)
            elif tag == "P3_ORDER":
                require(len(values) == 7, "Invalid order schema")
                job = integer(values[2])
                require(job not in run["orders"], f"Duplicate job {job}")
                release, finish, lead = map(number, values[3:6])
                reworks = integer(values[6])
                run["orders"][job] = (release, finish, lead, reworks)
            elif tag == "P3_DONE":
                require(len(values) == 6, "Invalid completion schema")
                run["done"] = (integer(values[2]), integer(values[3]),
                               number(values[4]), integer(values[5]))
            elif tag == "P3_METRIC":
                run["metrics"].append(_parse_metric(values))
            elif tag == "P3_CRN":
                match = re.fullmatch(r"P3_CRN,(-?\d+),(\d+),(\d+),(\d+),\[([^]]+)\],([^,]+)", line)
                require(match is not None, "Invalid CRN array schema")
                _, _, job, row, draws, quality = match.groups()
                job = integer(job)
                require(job not in run["crn"], "Duplicate CRN job")
                tape = (integer(row), *[number(x.strip()) for x in draws.split(",")], number(quality))
                require(len(tape) == 7 and tape[0] >= 0
                        and all(0 <= x < 1 for x in tape[1:]), "Invalid CRN values")
                run["crn"][job] = tape
            elif tag == "P3_STAGE":
                _, job, stage, visit, record = _parse_stage(values)
                skey = (job, stage, visit)
                require(skey not in run["stages"], f"Duplicate stage visit {skey}")
                run["stages"][skey] = record
            elif tag == "P3_KIT":
                job, record = _parse_kit(values)
                require(job not in run["kits"], f"Duplicate kit record {job}")
                run["kits"][job] = record
            else:
                raise ValueError(f"Unknown record: {tag}")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{path.name}:{lineno}: {exc}") from exc
    require(key is not None, f"{path.name}: no native records")
    run["key"] = key
    run["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return run


def max_visit(run, job, stage):
    """Highest visit index recorded for (job, stage); 0 if only the first visit exists."""
    visits = [v for (j, s, v) in run["stages"] if j == job and s == stage]
    return max(visits) if visits else 0
