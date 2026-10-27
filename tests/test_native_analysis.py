"""Small fabricated log fixtures test the analyzer; they are NOT simulation evidence."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location(
    "analyze_native", Path(__file__).resolve().parents[1] / "analysis" / "analyze_native.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


def fixture_text(seed=1, scenario=0, replay=False, service=1):
    """Two non-overlapping jobs, each taking one hour at every station."""
    lines = ["P3_META,SYNTHETIC",
             f"P3_CONFIG,{seed},{scenario},{str(replay).lower()},2,30.0,1.0,true,0.0,0.0,1,1,1,1,1"]
    for job in range(2):
        release = 10 * job
        lines.append(f"P3_CRN,{seed},{scenario},{job},0,[0.1, 0.2, 0.3, 0.4, 0.5],0.8")
        lines.append(f"P3_IN,{release},{job+1},{job},1")
        for stage in range(5):
            entered = release + stage * service
            lines.append(f"P3_STAGE,{seed},{scenario},{job},{stage},{entered},{entered},{entered+service},{service}")
        lines.append(f"P3_ORDER,{seed},{scenario},{job},{release},{release+5*service},{5*service},0")
        lines.append(f"P3_STATE,{release+5*service},{job+1},{job+1},0")
    horizon = 10 + 5 * service
    for stage in range(5):
        area = 0 if replay else 2 * service
        idle = 0 if replay else horizon - area
        lines.append(f"P3_METRIC,{seed},{scenario},{stage},{horizon},{area},0,{idle},0,0")
    lines.append(f"P3_DONE,{seed},{scenario},2,2,{horizon},2")
    return "\n".join(lines) + "\n"


def parse(tmp_path, text, name="fixture.log"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return native.parse_log(path)


def test_finite_metrics_use_entire_run_and_actual_capacity(tmp_path):
    run = parse(tmp_path, fixture_text(scenario=2))
    rep, stations, stages = native.validate_run(run, target=2)
    assert rep["mean_lead_h"] == rep["p90_lead_h"] == 5
    assert rep["mean_wip"] == pytest.approx(10 / 15)
    assert rep["throughput_per_h"] == pytest.approx(2 / 15)
    assert stations[1]["capacity"] == 2
    assert stations[1]["utilization"] == pytest.approx(2 / 30)
    assert stations[0]["utilization"] == pytest.approx(2 / 15)
    assert stations[0]["empty_station_idle_fraction"] == pytest.approx(13 / 15)
    assert all(row["mean_wait_h"] == 0 for row in stages)


@pytest.mark.parametrize("change,match", [
    (lambda x: x.rsplit("P3_DONE", 1)[0], "missing P3_DONE"),
    (lambda x: x.replace("P3_DONE,1,0,2,2,15,2", "P3_DONE,1,0,2,1,15,2"), "fully drain"),
    (lambda x: x.replace("P3_ORDER,1,0,1,10,15,5,0", "P3_ORDER,1,0,1,10,15,6,0"), "Invalid lead"),
    (lambda x: x.replace("P3_ORDER,1,0,1,10,15,5,0", "P3_ORDER,1,0,2,10,15,5,0"), "job IDs"),
    (lambda x: x.replace("P3_ORDER,1,0,1,10,15,5,0", "P3_ORDER,1,0,1,10,NaN,5,0"), "Non-finite"),
    (lambda x: x.replace(",30.0,1.0,true,", ",29.0,1.0,true,"), "config mismatch"),
    (lambda x: x.replace("P3_METRIC,1,0,2,15,2,0,13,0,0", "P3_METRIC,1,0,2,15,2,0,13,1,0"), "not drained"),
    (lambda x: x.replace("P3_METRIC,1,0,0,15,2,0,13,0,0", "P3_METRIC,1,0,0,15,1,0,13,0,0"), "integrals disagree"),
    (lambda x: x.replace("P3_STAGE,1,0,0,1,1,1,2,1", "P3_STAGE,1,0,0,1,1.2,1.2,2.2,1"), "stage chain"),
])
def test_bad_native_evidence_is_rejected(tmp_path, change, match):
    with pytest.raises(ValueError, match=match):
        native.validate_run(parse(tmp_path, change(fixture_text())), target=2)


def test_duplicate_job_rejected_even_if_terminal_counts_match(tmp_path):
    text = fixture_text().replace("P3_ORDER,1,0,1,10,15,5,0", "P3_ORDER,1,0,0,10,15,5,0")
    with pytest.raises(ValueError, match="Duplicate job"):
        parse(tmp_path, text)


def test_records_after_done_and_missing_config_rejected(tmp_path):
    with pytest.raises(ValueError, match="follow terminal"):
        parse(tmp_path, fixture_text() + "P3_ORDER,1,0,2,20,25,5,0\n")
    text = "\n".join(line for line in fixture_text().splitlines() if not line.startswith("P3_CONFIG"))
    with pytest.raises(ValueError, match="Missing synthetic/config"):
        native.validate_run(parse(tmp_path, text), target=2)


def matrix(tmp_path, seeds=(1, 2)):
    return [parse(tmp_path, fixture_text(seed, scenario), f"fixture-{seed}-{scenario}.log")
            for seed in seeds for scenario in range(6)]


def test_complete_paired_matrix_and_all_five_alternatives(tmp_path):
    runs = matrix(tmp_path)
    reps, stations, stages = native.validate_matrix(runs, [1, 2], target=2)
    summary, comparisons = native.summarize(reps)
    assert len(reps) == 12 and len(stations) == len(stages) == 60
    assert len(summary) == 24 and len(comparisons) == 20
    assert set(comparisons.scenario) == set(range(1, 6))
    assert comparisons["mean"].eq(0).all()
    assert comparisons.precision_status.eq("undefined_near_zero").all()
    native.write_outputs(runs, reps, stations, stages, tmp_path / "analysis", "finite")
    assert (tmp_path / "analysis" / "native_analysis.json").is_file()
    assert (tmp_path / "analysis" / "paired_lead_time.png").is_file()


def test_single_replication_keeps_points_without_claiming_a_ci(tmp_path, monkeypatch):
    runs = matrix(tmp_path, seeds=(1,))
    reps, stations, stages = native.validate_matrix(runs, [1], target=2)

    def reject_errorbars(*args, **kwargs):
        raise AssertionError("One replication has no estimable confidence interval")

    monkeypatch.setattr(native.plt.Axes, "errorbar", reject_errorbars)
    output = tmp_path / "single-replication"
    native.write_outputs(runs, reps, stations, stages, output, "finite")
    result = native.json.loads((output / "native_analysis.json").read_text())
    assert len(result["paired_comparisons"]) == 20
    assert all(row["half_width"] is None for row in result["paired_comparisons"])
    assert (output / "paired_lead_time.png").is_file()


@pytest.mark.parametrize("problem,match", [("missing", "matrix mismatch"), ("duplicate", "Duplicate seed"),
                                          ("crn", "CRN tape mismatch"), ("service", "CRN service mismatch")])
def test_matrix_and_common_random_numbers_are_enforced(tmp_path, problem, match):
    runs = matrix(tmp_path)
    if problem == "missing":
        runs.pop()
    elif problem == "duplicate":
        runs.append(runs[0])
    elif problem == "crn":
        runs[-1]["crn"][0] = (0, .9, .2, .3, .4, .5, .8)
    else:
        # Still a valid drained run, but one scenario uses different services.
        runs[-1] = parse(tmp_path, fixture_text(2, 5, service=1.1), "different-service.log")
    with pytest.raises(ValueError, match=match):
        native.validate_matrix(runs, [1, 2], target=2)


def test_student_ci_uses_replication_estimates():
    values = np.arange(1., 11.)
    result = native.confidence(values)
    expected_half = native.stats.t.ppf(.975, 9) * np.std(values, ddof=1) / np.sqrt(10)
    assert result["mean"] == 5.5
    assert result["half_width"] == pytest.approx(expected_half)
    assert result["precision_status"] == "more_replications_needed"


def test_absent_input_produces_no_outputs(tmp_path):
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="No native logs"):
        native.main(["--input", str(tmp_path / "missing"), "--output", str(output)])
    assert not output.exists()


def test_replay_is_separate_from_capacity_comparison(tmp_path):
    run = parse(tmp_path, fixture_text(replay=True))
    reps, stations, stages = native.validate_matrix([run], [1], mode="replay", target=2)
    assert stations.empty and len(stages) == 5
    summary, comparison = native.summarize(reps)
    assert comparison.empty
    assert summary.precision_status.eq("insufficient_replications").all()


def replay_source(tmp_path):
    source = tmp_path / "clean_orders.csv"
    # Deliberately unsorted: order IDs break ties exactly as in build_model.py.
    source.write_text(
        "order_id,release_h,kitting_h,assembly_h,test_h,quality_h,handover_h\n"
        "ORD-B,10,1,1,1,1,1\nORD-A,0,1,1,1,1,1\n", encoding="utf-8")
    return source


def test_replay_source_proves_every_stage_timestamp(tmp_path):
    run = parse(tmp_path, fixture_text(replay=True))
    native.validate_run(run, mode="replay", target=2)
    result = native.validate_replay_source([run], replay_source(tmp_path))
    assert result["clean_orders"] == 2
    assert result["maximum_absolute_error_h"] == 0
    assert len(result["sha256"]) == 64


@pytest.mark.parametrize("change", ["release", "stage", "wait", "count"])
def test_internally_consistent_wrong_replay_is_rejected(tmp_path, change):
    source = replay_source(tmp_path)
    text = fixture_text(replay=True, service=1.1 if change == "stage" else 1)
    if change == "release":
        # Shift a source release by one minute, while native run stays internally valid.
        source.write_text(source.read_text().replace("ORD-B,10,", "ORD-B,10.0166666667,"))
    elif change == "count":
        source.write_text(source.read_text() + "ORD-C,20,1,1,1,1,1\n")
    elif change == "wait":
        # This preserves chain/order and service durations but inserts a replay queue wait.
        text = text.replace("P3_STAGE,1,0,1,4,14,14,15,1", "P3_STAGE,1,0,1,4,14,15,16,1")
        text = text.replace("P3_ORDER,1,0,1,10,15,5,0", "P3_ORDER,1,0,1,10,16,6,0")
        text = text.replace("P3_STATE,15,2,2,0", "P3_STATE,16,2,2,0")
        text = text.replace(",4,15,0,0,0,0,0", ",4,16,0,0,0,0,0")
        # All station snapshots need the same new terminal time.
        text = "\n".join(line.replace(",15,0,0,0,0,0", ",16,0,0,0,0,0")
                         if line.startswith("P3_METRIC") else line for line in text.splitlines())
        text = text.replace("P3_DONE,1,0,2,2,15,2", "P3_DONE,1,0,2,2,16,2")
    run = parse(tmp_path, text)
    native.validate_run(run, mode="replay", target=2)
    with pytest.raises(ValueError, match="Replay source"):
        native.validate_replay_source([run], source)


def test_wrong_replay_cli_writes_no_outputs(tmp_path):
    path = tmp_path / "native-seed-1-scenario-0-replay.log"
    path.write_text(fixture_text(replay=True, service=1.1), encoding="utf-8")
    output = tmp_path / "rejected-output"
    with pytest.raises(ValueError, match="Replay source timestamp mismatch"):
        native.main(["--input", str(tmp_path), "--output", str(output), "--mode", "replay",
                     "--target", "2", "--calibration", str(replay_source(tmp_path))])
    assert not output.exists()


def mm1_fixture(seed=1):
    """Two hand-calculated queueing jobs; fabricated unit-test data only."""
    duration = -np.log(.5)
    release_times = [1., 1.1]
    finishes = [1 + duration, 1 + 2 * duration]
    horizon = finishes[-1]
    wait = finishes[0] - release_times[1]
    lines = ["P3_META,SYNTHETIC", "P3_VERIFICATION_MODE,MM1,lambda=0.5,mu=1.0",
             f"P3_CONFIG,{seed},0,false,2,2.0,1.0,true,0.0,0.0,1,1,1,1,1"]
    lines.extend([f'P3_IN,1.0,1,0,1',f'P3_IN,1.1,2,0,2',
                  f'P3_STATE,{finishes[0]},2,1,1',f'P3_STATE,{finishes[1]},2,2,0'])
    for job, (release, finish) in enumerate(zip(release_times, finishes)):
        start = finish - duration
        lines.append(f"P3_CRN,{seed},0,{job},0,[0.5, 0.2, 0.3, 0.4, 0.5],0.8")
        lines.append(f"P3_STAGE,{seed},0,{job},0,{release},{start},{finish},{duration}")
        for stage in range(1, 5):
            lines.append(f"P3_STAGE,{seed},0,{job},{stage},{finish},{finish},{finish},0")
        lines.append(f"P3_ORDER,{seed},0,{job},{release},{finish},{finish-release},0")
    lines.append(f"P3_METRIC,{seed},0,0,{horizon},{2*duration},{wait},1,0,0")
    for stage in range(1, 5):
        lines.append(f"P3_METRIC,{seed},0,{stage},{horizon},0,0,{horizon},0,0")
    lines.append(f"P3_DONE,{seed},0,2,2,{horizon},2")
    return "\n".join(lines) + "\n"


def test_mm1_reads_native_only_and_uses_full_drained_integrals(tmp_path):
    run = parse(tmp_path, mm1_fixture())
    row, stations, stages = native.validate_run(run, "mm1", target=2)
    duration = -np.log(.5)
    wait = duration - .1
    horizon = 1 + 2 * duration
    assert row["mean_wait_h"] == pytest.approx(wait / 2)
    assert row["mean_queue"] == pytest.approx(wait / horizon)
    assert row["mean_wip"] == pytest.approx((2 * duration + wait) / horizon)
    assert row["throughput_per_h"] == pytest.approx(2 / horizon)
    assert row["utilization"] == pytest.approx(2 * duration / horizon)
    assert len(stations) == len(stages) == 5


@pytest.mark.parametrize("change,match", [
    (lambda x: x.replace("P3_VERIFICATION_MODE,MM1,lambda=0.5,mu=1.0\n", ""), "Verification mode"),
    (lambda x: x.replace(",lambda=0.5,", ",lambda=0.6,"), "verification mode"),
    (lambda x: x.replace(",2,2.0,1.0,", ",2,3.0,1.0,"), "config mismatch"),
    (lambda x: x.replace("[0.5, 0.2", "[0.4, 0.2"), "exponential service tape"),
    (lambda x: x.rsplit("P3_DONE", 1)[0], "missing P3_DONE"),
])
def test_mm1_rejects_wrong_mode_configuration_and_service_tape(tmp_path, change, match):
    with pytest.raises(ValueError, match=match):
        native.validate_run(parse(tmp_path, change(mm1_fixture())), "mm1", target=2)


def test_finite_model_rejects_zero_service_duration(tmp_path):
    run = parse(tmp_path, fixture_text())
    run["stages"][(0, 0)] = (0., 0., 0., 0.)
    with pytest.raises(ValueError, match="Invalid stage times"):
        native.validate_run(run, target=2)


def test_mm1_benchmark_requires_coverage_accuracy_and_precision():
    frame = native.pd.DataFrame({metric: target * (1 + np.linspace(-.01, .01, 10))
                                 for metric, target in native.MM1_TARGETS.items()})
    accepted = native.assess_mm1(frame)
    assert accepted["accepted"] and len(accepted["checks"]) == 6
    inaccurate = frame * 1.2
    assert not native.assess_mm1(inaccurate)["accepted"]
    imprecise = native.pd.DataFrame({metric: target * (1 + np.linspace(-.9, .9, 10))
                                    for metric, target in native.MM1_TARGETS.items()})
    assert not native.assess_mm1(imprecise)["accepted"]
    assert not native.assess_mm1(frame.iloc[:1])["accepted"]


def test_mm1_outputs_actual_rejected_estimates_without_inventing_results(tmp_path):
    runs = [parse(tmp_path, mm1_fixture(seed), f"mm1-{seed}.log") for seed in (1, 2)]
    reps, stations, stages = native.validate_matrix(runs, [1, 2], "mm1", target=2)
    output = tmp_path / "mm1-analysis"
    native.write_outputs(runs, reps, stations, stages, output, "mm1")
    result = native.json.loads((output / "native_analysis.json").read_text())
    assert result["mm1_verification"]["accepted"] is False
    assert result["mm1_verification"]["checks"][0]["mean"] == pytest.approx(reps.mean_lead_h.mean())
    assert (output / "mm1_verification.csv").is_file()


@pytest.mark.parametrize("interarrival,scale", [(25., 1.), (40., 1.), (30., .75), (30., 1.25)])
def test_finite_sensitivity_configuration_must_match_declared_expectation(tmp_path, interarrival, scale):
    runs = matrix(tmp_path)
    for run in runs:
        run["config"].update(interarrival=interarrival, scale=scale)
    reps, _, _ = native.validate_matrix(runs, [1, 2], target=2,
                                         interarrival=interarrival, service_scale=scale)
    assert len(reps) == 12
    with pytest.raises(ValueError, match="config mismatch"):
        native.validate_matrix(runs, [1, 2], target=2)
    runs[-1]["config"]["scale"] = scale * 1.01
    with pytest.raises(ValueError, match="config mismatch"):
        native.validate_matrix(runs, [1, 2], target=2,
                               interarrival=interarrival, service_scale=scale)


@pytest.mark.parametrize("option,value", [("--interarrival", "nan"), ("--interarrival", "inf"),
                                        ("--interarrival", "0"), ("--interarrival", "-1"),
                                        ("--service-scale", "nan"), ("--service-scale", "inf"),
                                        ("--service-scale", "0"), ("--service-scale", "-1")])
def test_cli_rejects_nonpositive_or_nonfinite_sensitivity_settings(tmp_path, option, value):
    with pytest.raises(ValueError, match="finite and positive"):
        native.main(["--input", str(tmp_path), option, value])


@pytest.mark.parametrize("mode", ["replay", "mm1"])
@pytest.mark.parametrize("option,value", [("--interarrival", "25"), ("--service-scale", ".75")])
def test_sensitivity_settings_rejected_outside_finite_mode(tmp_path, mode, option, value):
    with pytest.raises(ValueError, match="require finite mode"):
        native.main(["--input", str(tmp_path), "--mode", mode, option, value])
