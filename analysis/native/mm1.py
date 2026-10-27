"""M/M/1 (v1, unchanged) and M/M/c (v2, new) analytic verification. SYNTHETIC educational data."""
from __future__ import annotations

from .metrics import confidence
from .parsing import MM1_TARGETS, require


def assess_mm1(frame):
    """Compare native finite-run estimates to the M/M/1 steady-state benchmark."""
    checks = []
    for metric, target in MM1_TARGETS.items():
        estimate = confidence(frame[metric])
        error = abs(estimate["mean"] - target) / target
        covered = (estimate["ci95_low"] is not None
                   and estimate["ci95_low"] <= target <= estimate["ci95_high"])
        precise = estimate["relative_half_width"] is not None and estimate["relative_half_width"] <= .05
        checks.append(dict(metric=metric, target=target, relative_error=error,
                           target_inside_ci95=covered, accepted=bool(covered and precise and error <= .05),
                           **estimate))
    return dict(accepted=all(row["accepted"] for row in checks), arrival_rate=.5, service_rate=1.,
                nominal_rho=.5, criteria="Every target inside its marginal 95% t CI; relative error <=5%; relative CI half-width <=5% of estimate. No simultaneous-coverage claim.",
                finite_run_bias="Empty start and complete drain; no warmup. Finite-run estimates approach but are not identical to steady-state expectations.",
                checks=checks)


def erlang_c(c: int, lam: float, mu: float):
    """Classic Erlang-B recursion converted to Erlang-C (probability an arrival must wait)."""
    require(c >= 1 and lam > 0 and mu > 0, "Invalid M/M/c parameters")
    a = lam / mu
    rho = a / c
    require(rho < 1, "M/M/c requires rho < 1 for a steady state to exist")
    b_prev = 1.0  # Erlang B_0 = 1
    for k in range(1, c + 1):
        b_prev = (a * b_prev) / (k + a * b_prev)
    b_c = b_prev
    p_wait = c * b_c / (c - a * (1 - b_c))
    return p_wait, rho


def mmc_targets(c: int, lam: float, mu: float) -> dict:
    p_wait, rho = erlang_c(c, lam, mu)
    wq = p_wait / (c * mu - lam)
    w = wq + 1.0 / mu
    lq = lam * wq
    l = lam * w
    return dict(mean_lead_h=w, mean_wait_h=wq, mean_wip=l, mean_queue=lq,
                throughput_per_h=lam, utilization=rho)


def assess_mmc(frame, c: int, lam: float, mu: float):
    """Compare native finite-run estimates to Erlang-C M/M/c analytic targets."""
    targets = mmc_targets(c, lam, mu)
    checks = []
    for metric, target in targets.items():
        estimate = confidence(frame[metric])
        error = abs(estimate["mean"] - target) / target if target else None
        covered = (estimate["ci95_low"] is not None
                   and estimate["ci95_low"] <= target <= estimate["ci95_high"])
        precise = (estimate["relative_half_width"] is not None
                   and estimate["relative_half_width"] <= .05)
        checks.append(dict(metric=metric, target=target, relative_error=error,
                           target_inside_ci95=covered,
                           accepted=bool(covered and precise and error is not None and error <= .05),
                           **estimate))
    return dict(accepted=all(row["accepted"] for row in checks), servers=c, arrival_rate=lam,
                service_rate=mu, nominal_rho=targets["utilization"],
                criteria="Same acceptance pattern as M/M/1: every analytic target inside its "
                         "marginal 95% t CI, relative error <=5%, relative CI half-width <=5%.",
                finite_run_bias="Empty start and complete drain; no warmup. Finite-run estimates "
                               "approach but are not identical to steady-state expectations.",
                checks=checks)
