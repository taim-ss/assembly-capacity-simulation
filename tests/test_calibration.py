"""Verification of SYNTHETIC calibration; no claim about real service/capacity."""
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p3_calibrate", ROOT/"analysis/calibrate.py")
cal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cal)


@pytest.fixture(scope="module")
def source_data():
    return cal.read_source(cal.DEFAULT_SOURCE)


def test_exact_workbook_whole_order_exclusions_and_missing_precedence(source_data):
    raw, clean, _, _, _ = source_data
    assert len(raw) == 200 and len(clean) == 195
    rejected = raw[raw.quality_flag != "OK"]
    assert dict(zip(rejected.order_id, rejected.quality_flag)) == {
        "ORD-0166": "Missing timestamp", "ORD-0162": "Missing timestamp",
        "ORD-0012": "Missing timestamp", "ORD-0195": "Negative duration",
        "ORD-0053": "Negative duration"}
    assert clean[cal.TIMES].notna().all().all()
    assert (clean[cal.HOURS] > 0).all().all()
    assert not set(rejected.order_id) & set(clean.order_id)


def test_elapsed_reconstruction_and_population_boundaries(source_data):
    raw, clean, _, expected, limitation = source_data
    assert "waiting time" in limitation
    assert np.isclose(clean.assembly_elapsed_h.mean(), 20.176153846153845)
    assert np.isclose(clean.test_elapsed_h.quantile(.9), 33.86666666666667)
    assert np.isclose(clean.end_to_end_elapsed_h.mean(), expected["end_to_end_mean_h"])
    assert np.isclose(clean.end_to_end_elapsed_h.quantile(.9), expected["end_to_end_p90_h"])
    assert np.allclose(clean[cal.HOURS].sum(axis=1), clean.end_to_end_elapsed_h)
    assert np.allclose(clean.release_h, (clean.release-raw.release.min()).dt.total_seconds()/3600)
    assert np.allclose(clean.quality_h, clean.quality_release_elapsed_h)
    ar, gaps, _ = cal.arrivals(raw)
    assert ar["n_all_releases"] == 200 and ar["n_gaps"] == 199
    assert gaps.min() > 0 and np.isclose(gaps.mean(), 5.054020100502513)


def test_reordered_workbook_keeps_chronology_gap_ids_and_source_rows(monkeypatch, source_data):
    original_raw, original_clean, *_ = source_data
    workbook = cal.load_workbook(cal.DEFAULT_SOURCE, read_only=True, data_only=True)
    sheet = workbook["LeadTime_Analysis"]
    rows = list(sheet.iter_rows(min_row=6, max_row=205, max_col=13, values_only=True))
    monkeypatch.setattr(sheet, "iter_rows", lambda **kwargs: iter(reversed(rows)))
    close = Mock(wraps=workbook.close)
    monkeypatch.setattr(workbook, "close", close)
    monkeypatch.setattr(cal, "load_workbook", lambda *args, **kwargs: workbook)

    raw, clean, *_ = cal.read_source(cal.DEFAULT_SOURCE)

    close.assert_called_once()
    assert raw.release.is_monotonic_increasing
    assert clean.order_id.tolist() == original_clean.order_id.tolist()
    assert raw.order_id.tolist() == original_raw.order_id.tolist()
    assert raw.source_row.tolist() == (211-original_raw.source_row).tolist()
    _, gaps, _ = cal.arrivals(raw)
    release_by_id = raw.set_index("order_id").release
    expected_gaps = np.array([
        (release_by_id[current]-release_by_id[previous]).total_seconds()/3600
        for previous, current in zip(raw.order_id.iloc[:-1], raw.order_id.iloc[1:])
    ])
    assert np.allclose(gaps, expected_gaps)


def test_workbook_closes_when_quality_flag_validation_fails(monkeypatch):
    workbook = cal.load_workbook(cal.DEFAULT_SOURCE, read_only=True, data_only=True)
    sheet = workbook["LeadTime_Analysis"]
    rows = list(sheet.iter_rows(min_row=6, max_row=205, max_col=13, values_only=True))
    rows[0] = (*rows[0][:12], "Invalid cached flag")
    monkeypatch.setattr(sheet, "iter_rows", lambda **kwargs: iter(rows))
    close = Mock(wraps=workbook.close)
    monkeypatch.setattr(workbook, "close", close)
    monkeypatch.setattr(cal, "load_workbook", lambda *args, **kwargs: workbook)

    with pytest.raises(ValueError, match="quality flags disagree"):
        cal.read_source(cal.DEFAULT_SOURCE)

    close.assert_called_once()


@pytest.mark.parametrize("family", list(cal.FAMILIES))
def test_fits_have_fixed_zero_location_and_positive_draws(family):
    x = np.random.default_rng(77).lognormal(2, .4, 200)
    params = cal.fit_family(x, family)
    assert params[1] == 0 and params[0] > 0 and params[-1] > 0
    draws = cal.sample_model(x, family, params, 1000, np.random.default_rng(88))
    assert np.isfinite(draws).all() and (draws > 0).all()
    cdf = cal.cdf_at(x, np.sort(x), family, params)
    assert (np.diff(cdf) >= 0).all() and ((cdf >= 0) & (cdf <= 1)).all()


def test_whole_order_bootstrap_preserves_linear_dependency():
    x = np.arange(1, 31, dtype=float)
    mean_ci, p90_ci = cal.bootstrap_summary(np.column_stack([x, 3*x]), 500)
    assert np.allclose(mean_ci[:, 1], 3*mean_ci[:, 0])
    assert np.allclose(p90_ci[:, 1], 3*p90_ci[:, 0])
    assert np.all(mean_ci[0] < mean_ci[1])


def test_generated_output_provenance_models_and_no_false_validation():
    p = ROOT/"analysis/calibration"
    summary = json.loads((p/"summary.json").read_text(encoding="utf-8"))
    assert summary["source_sha256"] == hashlib.sha256(cal.DEFAULT_SOURCE.read_bytes()).hexdigest()
    assert summary["source_unchanged"]
    assert not summary["service_times_identifiable"]
    assert not summary["capacities_identifiable"]
    assert "not independent final validation" in summary["selection"]
    fits = pd.read_csv(p/"fit_diagnostics.csv")
    assert len(fits) == 20
    assert set(fits.family) == {"gamma", "lognormal", "weibull", "empirical"}
    selected = pd.read_csv(p/"calibration_table.csv")
    assert len(selected) == 5
    for _, row in selected.iterrows():
        assert np.isclose(row.chronological_selection_cdf_rmse,
                          fits.loc[fits.step == row.step, "chronological_selection_cdf_rmse"].min())
    for csv in [*p.glob("*.csv"), *(ROOT/"results/calibration").glob("*.csv")]:
        assert "SYNTHETIC" in csv.read_text(encoding="utf-8")
