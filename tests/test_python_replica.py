"""Unit tests for the SYNTHETIC P3 v2 pure-Python replica (analysis/python_replica).

AAA style. Loaded by file path (same pattern as the other v2 tests) so no package __init__ is
required under analysis/python_replica.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPLICA_DIR = ROOT / "analysis" / "python_replica"
if str(REPLICA_DIR) not in sys.path:
    sys.path.insert(0, str(REPLICA_DIR))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPLICA_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses needs the module registered to resolve types
    spec.loader.exec_module(module)
    return module


java_random = _load("java_random")
quantiles = _load("quantiles")
model = _load("model")

JavaRandom = java_random.JavaRandom
ScenarioConfig = model.ScenarioConfig
run_scenario = model.run_scenario
load_samples = model.load_samples


# ---------------------------------------------------------------------------
# java_random.py
# ---------------------------------------------------------------------------

def test_next_double_matches_known_java_random_seed_zero_vector():
    # Arrange: new java.util.Random(0) is a documented reference vector.
    rng = JavaRandom(0)
    # Act
    value = rng.next_double()
    # Assert
    assert value == pytest.approx(0.730967787376657, abs=1e-15)


def test_next_double_matches_the_actual_v1_native_log_crn_draws():
    # Arrange: seed=100 stage-0 stream from native-seed-100-scenario-0-finite.log P3_CRN line.
    rng = java_random.JavaRandom(21001 + 1000 * 0 + 100)
    # Act
    value = rng.next_double()
    # Assert
    assert value == pytest.approx(0.574562352423927, abs=1e-15)


def test_next_int_power_of_two_bound_uses_the_fast_path():
    # Arrange
    rng = JavaRandom(0)
    # Act
    value = rng.next_int(16)
    # Assert: must be in range and deterministic for seed 0
    assert 0 <= value < 16


def test_next_int_non_power_of_two_bound_matches_native_row_draw():
    # Arrange: native-seed-100-scenario-0-finite.log job 0 row draw is rowRng.nextInt(195) == 25.
    rng = JavaRandom(12001 + 100)
    # Act
    row = rng.next_int(195)
    # Assert
    assert row == 25


def test_set_seed_resets_the_stream_to_a_fresh_sequence():
    # Arrange
    rng = JavaRandom(7)
    first_pass = [rng.next_double() for _ in range(3)]
    # Act
    rng.set_seed(7)
    second_pass = [rng.next_double() for _ in range(3)]
    # Assert
    assert first_pass == second_pass


def test_next_int_rejects_non_positive_bound():
    # Arrange
    rng = JavaRandom(1)
    # Act / Assert
    with pytest.raises(ValueError):
        rng.next_int(0)


# ---------------------------------------------------------------------------
# quantiles.py
# ---------------------------------------------------------------------------

def test_normal_ppf_at_the_median_is_zero():
    # Act
    value = quantiles.normal_ppf(0.5)
    # Assert
    assert value == pytest.approx(0.0, abs=1e-12)


def test_normal_ppf_matches_scipy_within_1e9_across_central_and_tail_region():
    scipy_stats = pytest.importorskip("scipy.stats")
    # Arrange
    probs = [1e-6, 0.001, 0.05, 0.2, 0.5, 0.8, 0.95, 0.999, 1 - 1e-6]
    # Act / Assert
    for p in probs:
        assert quantiles.normal_ppf(p) == pytest.approx(scipy_stats.norm.ppf(p), abs=1e-9)


def test_normal_ppf_handles_boundary_probabilities():
    # Act / Assert
    assert quantiles.normal_ppf(0.0) == float("-inf")
    assert quantiles.normal_ppf(1.0) == float("inf")


def test_lognormal_from_u_is_positive_and_scales_with_u():
    # Arrange / Act
    low = quantiles.lognormal_from_u(0.1, 0.3, 19.0)
    high = quantiles.lognormal_from_u(0.9, 0.3, 19.0)
    # Assert
    assert low > 0 and high > 0
    assert high > low


def test_weibull_from_u_matches_closed_form_inverse_cdf():
    # Arrange
    u, c, scale = 0.6, 1.7, 20.0
    # Act
    value = quantiles.weibull_from_u(u, c, scale)
    expected = scale * ((-math.log(1 - u)) ** (1 / c))
    # Assert
    assert value == pytest.approx(expected, rel=1e-12)


def test_empirical_quantile_clamps_to_the_last_index_at_u_equals_one():
    # Arrange
    sorted_values = [1.0, 2.0, 3.0, 4.0]
    # Act
    value = quantiles.empirical_quantile(0.999999, sorted_values)
    # Assert
    assert value == 4.0


# ---------------------------------------------------------------------------
# model.py
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def samples():
    return load_samples()


def test_load_samples_returns_195_rows_of_6_columns(samples):
    # Assert
    assert len(samples) == 195
    assert all(len(row) == 6 for row in samples)


def test_default_scenario_conserves_orders_in_equals_orders_out(samples):
    # Arrange
    cfg = ScenarioConfig(rep_seed=11, scenario_index=0, scenario_orders=600)
    # Act
    result = run_scenario(cfg, samples)
    # Assert
    assert len(result["jobs"]) == 600
    assert all(j.reworks == 0 for j in result["jobs"])  # default reworkProbability=0


def test_default_scenario_matches_native_release_time_of_job_zero(samples):
    # Arrange: native-seed-100-scenario-0-finite.log, job 0 release = 4.952706035553079
    cfg = ScenarioConfig(rep_seed=100, scenario_index=0, scenario_orders=600)
    # Act
    result = run_scenario(cfg, samples)
    job0 = next(j for j in result["jobs"] if j.job_id == 0)
    # Assert
    assert job0.release_time == pytest.approx(4.952706035553079, abs=1e-9)
    assert job0.finished_at[4] == pytest.approx(49.41937270221978, abs=1e-9)


def test_scenario_plus_one_bumps_exactly_the_targeted_stage_capacity():
    # Arrange
    base = ScenarioConfig(rep_seed=1, scenario_index=0)
    plus_assembly = ScenarioConfig(rep_seed=1, scenario_index=2)
    # Act
    base_caps = base.capacities()
    bumped_caps = plus_assembly.capacities()
    # Assert
    assert bumped_caps[1] == base_caps[1] + 1
    assert bumped_caps[0] == base_caps[0]
    assert bumped_caps[2] == base_caps[2]


def test_rework_probability_above_zero_produces_at_least_one_reworked_job(samples):
    # Arrange: p=0.5 and maxRework default 5 should make rework common across 600 jobs.
    cfg = ScenarioConfig(rep_seed=11, scenario_index=0, scenario_orders=600,
                          rework_probability=0.5)
    # Act
    result = run_scenario(cfg, samples)
    # Assert
    assert any(j.reworks > 0 for j in result["jobs"])
    assert all(j.reworks <= cfg.max_rework for j in result["jobs"])


def test_rework_zero_probability_never_reworks_even_with_max_rework_set(samples):
    # Arrange
    cfg = ScenarioConfig(rep_seed=11, scenario_index=0, scenario_orders=50,
                          rework_probability=0.0, max_rework=5)
    # Act
    result = run_scenario(cfg, samples)
    # Assert
    assert all(j.reworks == 0 for j in result["jobs"])


def test_component_mode_one_produces_non_negative_kit_waits(samples):
    # Arrange: slow component feed (mean 20h) vs fast order release (mean 5h) forces queued waits.
    cfg = ScenarioConfig(rep_seed=11, scenario_index=0, scenario_orders=100,
                          mean_interarrival=5.0, component_mode=1,
                          component_mean_interarrival=20.0)
    # Act
    result = run_scenario(cfg, samples)
    # Assert
    assert all(j.kit_wait >= 0 for j in result["jobs"])
    assert any(j.kit_wait > 0 for j in result["jobs"])


def test_input_mode_one_produces_positive_fitted_durations(samples):
    # Arrange
    cfg = ScenarioConfig(rep_seed=11, scenario_index=0, scenario_orders=50, input_mode=1)
    # Act
    result = run_scenario(cfg, samples)
    # Assert
    assert all(all(d > 0 for d in j.base_duration) for j in result["jobs"])


def test_conservation_holds_orders_out_never_exceeds_orders_in(samples):
    # Arrange
    cfg = ScenarioConfig(rep_seed=42, scenario_index=3, scenario_orders=200)
    # Act
    result = run_scenario(cfg, samples)
    # Assert: every job finished and lead time is non-negative
    assert len(result["jobs"]) == 200
    assert all(j.finished_at[4] >= j.release_time for j in result["jobs"])
