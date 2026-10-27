"""Fabricated replication tables test analysis arithmetic, never native-run evidence."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ANALYSIS = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ANALYSIS))
SPEC = importlib.util.spec_from_file_location("summarize_decision", ANALYSIS / "summarize_decision.py")
decision = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(decision)
sys.path.pop(0)


def replication_fixture():
    rows = []
    for seed in range(1, 11):
        for scenario in range(6):
            improvement = (0., .1, 2., 3., .2, 0.)[scenario]
            rows.append(dict(seed=seed, scenario=scenario, target=600, final_time_h=18000.,
                             mean_lead_h=50 + seed - improvement,
                             p90_lead_h=80 + 2*seed - 2*improvement,
                             mean_wip=2 + .01*seed - .01*improvement,
                             throughput_per_h=.033 + .00001*seed))
    return pd.DataFrame(rows)


def test_direct_assembly_test_ci_pairs_same_seed_despite_row_order():
    frame = replication_fixture().sample(frac=1., random_state=4)
    direct = decision.compare_assembly_test(frame)
    mean = direct[direct.metric == "mean_lead_h"].iloc[0]
    assert mean["mean"] == pytest.approx(1.)
    assert mean.ci95_low == mean.ci95_high == pytest.approx(1.)
    assert mean.positive_means == "Test +1 improves over Assembly +1"


def test_holm_adjustment_is_monotone_and_restores_original_order():
    adjusted = decision.holm_adjust([.03, .001, .01, .2, .049])
    assert adjusted == pytest.approx([.09, .005, .04, .2, .098])


def test_all_five_capacity_alternatives_are_retained_even_zero_effects():
    effects = decision.paired_effects(replication_fixture())
    assert len(effects) == 20
    assert set(effects.scenario) == set(range(1, 6))
    zero = effects[(effects.scenario == 5) & (effects.metric == "mean_lead_h")].iloc[0]
    assert zero["mean"] == 0
    assert zero.holm_p == 1
    assert zero.absolute_precision_met
    assert not zero.precision_under_5pct


def test_fieller_cost_ratio_has_paired_uncertainty_and_rejects_near_zero_denominator():
    denominator = np.linspace(1.8, 2.2, 10)
    result = decision.fieller_ratio(np.full(10, 100.), denominator)
    assert result["estimate"] == pytest.approx(50.)
    assert result["ci95_low"] < 50 < result["ci95_high"]
    assert decision.fieller_ratio([100., 100.], [-1., 1.])["estimate"] is None
    assert decision.fieller_ratio([100., 100.], [-1., 2.])["estimate"] is None


def test_cost_units_use_campaign_cost_over_accumulated_order_lead_hours():
    frame = replication_fixture()
    costs = decision.hypothetical_costs(frame, decision.paired_effects(frame))
    assembly = costs[costs.scenario == 2].iloc[0]
    assert assembly.mean_campaign_cost == 35 * 18000
    assert assembly.mean_saved_order_lead_hours == 600 * 2
    assert assembly.lead_savings_ratio == pytest.approx(525.)
    assert "accumulated order-lead-hour" in assembly.lead_savings_cost_units
    assert costs.incremental_unit_cost.isna().all()
    assert costs.incremental_unit_cost_ci95_low.isna().all()
    assert costs[costs.scenario == 5].lead_savings_ratio.isna().all()


def test_positive_throughput_cost_ratio_inverts_the_gain_interval():
    frame = replication_fixture()
    for seed in range(1, 11):
        frame.loc[(frame.seed == seed) & (frame.scenario == 2), "throughput_per_h"] += .001 + seed*.000001
    effects = decision.paired_effects(frame)
    gain = effects[(effects.scenario == 2) & (effects.metric == "throughput_per_h")].iloc[0]
    cost = decision.hypothetical_costs(frame, effects).set_index("scenario").loc[2]
    assert cost.incremental_unit_cost == pytest.approx(35/gain["mean"])
    assert cost.incremental_unit_cost_ci95_low == pytest.approx(35/gain.ci95_high)
    assert cost.incremental_unit_cost_ci95_high == pytest.approx(35/gain.ci95_low)


def test_precision_does_not_silently_choose_absolute_rule_for_large_effect():
    result = decision.precision(np.linspace(0., 1., 10), "mean_lead_h")
    assert result["absolute_precision_met"]
    assert not result["precision_under_5pct"]
    assert result["absolute_tolerance"] == .5


def test_missing_confirmation_writes_no_outputs(tmp_path):
    output = tmp_path / "decision"
    with pytest.raises(ValueError, match="Missing analyzed native inputs"):
        decision.main(["--results", str(tmp_path), "--output", str(output)])
    assert not output.exists()


def test_native_loader_checks_matrix_manifest_and_expected_settings(tmp_path):
    frame = replication_fixture()
    station_rows = [dict(seed=seed, scenario=scenario, stage=stage,
                         utilization=.2, mean_queue=.1, empty_station_idle_fraction=.8)
                    for seed in range(1, 11) for scenario in range(6) for stage in decision.STAGES]
    frame.to_csv(tmp_path / "replications.csv", index=False)
    pd.DataFrame(station_rows).to_csv(tmp_path / "station_replications.csv", index=False)
    meta = dict(mode="finite", label="SYNTHETIC - actual AnyLogic native output",
                configuration=dict(interarrival=30., scale=1.),
                inputs=[dict(seed=seed, scenario=scenario) for seed in range(1, 11) for scenario in range(6)])
    manifest = tmp_path / "native_analysis.json"
    manifest.write_text(decision.json.dumps(meta))
    loaded, stations, hashes = decision.load_bundle(tmp_path, list(range(1, 11)))
    assert len(loaded) == 60 and len(stations) == 300 and len(hashes) == 3
    assert all(len(item["sha256"]) == 64 for item in hashes)
    with pytest.raises(ValueError, match="settings mismatch"):
        decision.load_bundle(tmp_path, list(range(1, 11)), interarrival=25.)
    meta["inputs"].pop()
    manifest.write_text(decision.json.dumps(meta))
    with pytest.raises(ValueError, match="provenance manifest"):
        decision.load_bundle(tmp_path, list(range(1, 11)))
