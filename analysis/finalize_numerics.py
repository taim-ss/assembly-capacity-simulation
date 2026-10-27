"""Final SYNTHETIC P3 diagnostics from accepted native logs, never a simulator."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

from native.comparisons import primary_contrast, summarize
from native.metrics import confidence
from native.parsing import _parse_config, require

ROOT = Path(__file__).resolve().parents[1]
KPI = ['mean_lead_h', 'p90_lead_h', 'mean_wip', 'throughput_per_h']
STAGE_COLUMNS = dict(Kitting='kitting_h', Assembly='assembly_h', Test='test_h',
                     Quality='quality_h', Handover='handover_h',
                     Total='end_to_end_elapsed_h')


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf8')


def selected_records(path, expected_sha):
    """Hash exact bytes while parsing only configuration, orders and completion."""
    digest = hashlib.sha256()
    orders, config, done = {}, None, None
    with path.open('rb') as stream:
        for raw in stream:
            digest.update(raw)
            if not raw.startswith((b'P3_ORDER,', b'P3_CONFIG,', b'P3_DONE,')):
                continue
            tag, *values = raw.decode('utf8').strip().split(',')
            if tag == 'P3_CONFIG':
                require(config is None, f'Duplicate config: {path.name}')
                config = _parse_config(values)
            elif tag == 'P3_DONE':
                require(done is None, f'Duplicate completion: {path.name}')
                done = (int(values[2]), int(values[3]), float(values[4]), int(values[5]))
            else:
                job = int(values[2])
                require(job not in orders, f'Duplicate order: {path.name}/{job}')
                orders[job] = tuple(map(float, values[3:6]))
    actual_sha = digest.hexdigest()
    require(actual_sha == expected_sha, f'Native evidence hash changed: {path.name}')
    require(config is not None and done is not None, f'Incomplete native run: {path.name}')
    target = config['target']
    require(done[0] == done[1] == done[3] == target, f'Incomplete cohort: {path.name}')
    require(set(orders) == set(range(target)), f'Order cohort mismatch: {path.name}')
    array = np.array([orders[job] for job in range(target)], dtype=float)
    require(np.max(np.abs(array[:, 1] - array[:, 0] - array[:, 2])) < 1e-9,
            f'Invalid order durations: {path.name}')
    return config, done[2], array


def warmup_sensitivity():
    accepted = ROOT/'results/analysis/e2-confirmation/acceptance.json'
    provenance = json.loads(accepted.read_text(encoding='utf8'))
    require(provenance['runs'] == 1200 and provenance['full_job_crn_checked'],
            'Missing prior strict native acceptance')
    inputs = provenance['inputs']
    expected = {(seed, scenario) for seed in range(11, 211) for scenario in range(6)}
    require({(x['seed'], x['scenario']) for x in inputs} == expected,
            'Invalid accepted native grid')
    source = ROOT/'results/native/remaining/e2-confirmation'
    require({p.name for p in source.glob('native-seed-*.log')} == {x['file'] for x in inputs},
            'Missing/extra native logs')
    records = []
    for index, item in enumerate(inputs, 1):
        c, horizon, orders = selected_records(source/item['file'], item['sha256'])
        require((c['seed'], c['scenario']) == (item['seed'], item['scenario']),
                'Native key/provenance mismatch')
        require(c['target'] == 5000 and not c['replay'], 'Wrong E2 configuration')
        for cutoff in (250, 500, 1000):
            start = orders[cutoff, 0]
            duration = horizon-start
            leads = orders[cutoff:, 2]
            area = np.maximum(0., np.minimum(orders[:, 1], horizon)
                              - np.maximum(orders[:, 0], start)).sum()
            records.append(dict(warmup_jobs=cutoff, seed=c['seed'], scenario=c['scenario'],
                mean_lead_h=float(leads.mean()), p90_lead_h=float(np.quantile(leads, .9)),
                mean_wip=float(area/duration), throughput_per_h=len(leads)/duration,
                window_hours=duration))
        if index % 100 == 0:
            print(f'Warm-up sensitivity: {index}/1200 native hashes checked', flush=True)
    frame = pd.DataFrame(records)
    out = ROOT/'results/warmup-sensitivity'
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out/'replications.csv', index=False)
    summaries, primary, effects = [], [], []
    for cutoff, subset in frame.groupby('warmup_jobs'):
        summary, effect = summarize(subset)
        direct = primary_contrast(subset)
        for data, collection in [(summary, summaries), (effect, effects), (direct, primary)]:
            data.insert(0, 'warmup_jobs', cutoff)
            collection.append(data)
    for name, collection in [('summary', summaries), ('effects', effects), ('primary', primary)]:
        pd.concat(collection, ignore_index=True).to_csv(out/(name+'.csv'), index=False)
    original = pd.read_csv(ROOT/'results/analysis/e2-confirmation/replications.csv').set_index(['seed', 'scenario'])
    reproduced = frame[frame.warmup_jobs == 500].set_index(['seed', 'scenario']).loc[original.index]
    maximum = {key: float(np.max(np.abs(original[key]-reproduced[key])))
               for key in KPI+['window_hours']}
    passed = all(value <= 1e-9 for value in maximum.values())
    save_json(out/'acceptance.json', dict(label='SYNTHETIC actual native cutoff sensitivity',
        native_runs=1200, cutoffs=[250, 500, 1000], all_raw_sha256_rechecked=True,
        accepted_input_manifest=str(accepted.relative_to(ROOT)),
        accepted_manifest_sha256=hashlib.sha256(accepted.read_bytes()).hexdigest(),
        w500_reproduction_pass=passed, maximum_absolute_difference=maximum,
        interpretation='Post-cutoff finite drained cohorts; no perpetual steady-state claim.'))
    require(passed, 'W500 reproduction differs from original accepted values')
    print('W500 reproduction passed: '+str(maximum), flush=True)


def source_targets():
    clean = pd.read_csv(ROOT/'analysis/calibration/clean_orders.csv')
    return {stage: {'mean_lead_h': float(clean[column].mean()),
                    'p90_lead_h': float(clean[column].quantile(.9))}
            for stage, column in STAGE_COLUMNS.items()}


def validation():
    targets = source_targets()
    stages = pd.read_csv(ROOT/'results/analysis/e1-pilot/stages.csv')
    reps = pd.read_csv(ROOT/'results/analysis/e1-pilot/replications.csv')
    stations = pd.read_csv(ROOT/'results/analysis/e1-pilot/stations.csv')
    require(len(reps) == 10 and len(stages) == 50, 'Incomplete E1 pilot')
    rows = []
    for stage in STAGE_COLUMNS:
        for metric, tolerance in [('mean_lead_h', .10), ('p90_lead_h', .15)]:
            if stage == 'Total':
                values = reps[metric]
            else:
                column = 'mean_elapsed_h' if metric == 'mean_lead_h' else 'p90_elapsed_h'
                values = stages[stages.stage == stage][column]
            estimate = confidence(values)
            target = targets[stage][metric]
            error = abs(estimate['mean']-target)/target
            rows.append(dict(stage=stage, metric=metric, observed_h=target,
                allowed_relative_error=tolerance, relative_error=error,
                accuracy_band_pass=bool(error <= tolerance),
                observed_inside_replication_ci=bool(estimate['ci95_low'] <= target <= estimate['ci95_high']),
                **estimate))
    out = ROOT/'results/validation-v2'
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out/'e1-accuracy.csv', index=False)
    zero_wait = bool((stages.mean_wait_h.abs() <= 1e-9).all())
    zero_queue = bool((stations.mean_queue.abs() <= 1e-9).all())
    occupancy = stations.groupby('stage').utilization.agg(['mean', 'min', 'max']).reset_index()
    occupancy.to_csv(out/'e1-utilization.csv', index=False)
    e2 = pd.read_csv(ROOT/'results/analysis/e2-confirmation/summary.csv')
    comparisons = []
    for metric, tolerance in [('mean_lead_h', .10), ('p90_lead_h', .15)]:
        value = e2[(e2.scenario == 0) & (e2.metric == metric)].iloc[0]
        target = targets['Total'][metric]
        error = abs(float(value['mean'])-target)/target
        comparisons.append(dict(metric=metric, observed_h=target, native_mean_h=float(value['mean']),
            native_ci95_low=float(value.ci95_low), native_ci95_high=float(value.ci95_high),
            relative_error=error, allowed_relative_error=tolerance, accuracy_band_pass=bool(error <= tolerance)))
    pd.DataFrame(comparisons).to_csv(out/'e2-observed-comparison.csv', index=False)
    result = dict(label='SYNTHETIC internal no-wait consistency and observed-rate discrepancy',
        e1_accuracy_bands_pass=all(row['accuracy_band_pass'] for row in rows),
        all_native_waits_zero=zero_wait, all_native_mean_queues_zero=zero_queue,
        e1_utilization_range=[float(stations.utilization.min()), float(stations.utilization.max())],
        utilization_caveat='The preregistration says utilization ~0. Actual pool utilization is nonzero; zero queues/waits establish nonbinding capacity. No new utilization threshold is invented.',
        e2_accuracy_bands_pass=all(row['accuracy_band_pass'] for row in comparisons),
        e2_observed_comparisons=comparisons,
        interpretation='E1 verifies internal elapsed-as-service consistency only. Neither E1 nor E2 validates a real process or identifies capacities/service times.')
    save_json(out/'acceptance.json', result)
    print(json.dumps(result, indent=2), flush=True)


def manifold():
    points = pd.read_csv(ROOT/'results/plans/manifold-points.csv')
    rows = []
    for point in points.itertuples(index=False):
        family = f'e4-contrast-c{point.cap_assembly}-t{point.cap_test}'
        directory = ROOT/'results/analysis'/family
        accepted = json.loads((directory/'acceptance.json').read_text())
        require(accepted['runs'] == 30 and accepted['warmup_jobs'] == 500,
                f'Expected strict native contrast acceptance: {family}')
        frame = pd.read_csv(directory/'replications.csv')
        require(set(zip(frame.seed, frame.scenario)) == {(s, c) for s in range(1, 11) for c in (0, 2, 3)},
                f'Incomplete manifold contrast: {family}')
        baseline = confidence(frame[frame.scenario == 0].mean_lead_h)
        direct = primary_contrast(frame)
        for contrast in direct.to_dict('records'):
            rows.append(dict(cap_assembly=point.cap_assembly, cap_test=point.cap_test,
                service_scale=point.service_scale, native_baseline_mean_h=baseline['mean'],
                native_baseline_ci95_low=baseline['ci95_low'], native_baseline_ci95_high=baseline['ci95_high'],
                observed_target_h=point.target_mean_h, residual_h=baseline['mean']-point.target_mean_h,
                relative_residual=(baseline['mean']-point.target_mean_h)/point.target_mean_h,
                **contrast))
    out = ROOT/'results/manifold-summary'
    out.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(rows)
    result.to_csv(out/'contrasts.csv', index=False)
    sign_change = bool((result['mean'] > 0).any() and (result['mean'] < 0).any())
    if sign_change:
        sentence = ('The Assembly-over-Test preference is NOT identifiable from the observed data alone: '
            'at least one (capacity, waiting-share) pair that reproduces the observed mean lead time reverses '
            'which station should get the added unit. The recommendation in this report is conditional on '
            'the specific (c, s) chosen for E2, and that choice is an assumption, not an inference from data.')
    else:
        require(bool((result['mean'] > 0).all()), 'Preregistered stable-positive wording does not cover this outcome; report the gap rather than guess')
        sentence = ('The Assembly-over-Test preference is stable across the explored (capacity, waiting-share) '
            'manifold that reproduces the observed end-to-end mean; it is not an artifact of one arbitrarily chosen calibration point.')
    save_json(out/'acceptance.json', dict(label='SYNTHETIC native E4 capacity/service manifold',
        native_runs=120, points=4, seeds_per_scenario=10, pointwise_not_simultaneous=True,
        ranking_point_estimates_change_sign=sign_change, preregistered_sentence=sentence,
        maximum_absolute_baseline_residual_h=float(result.residual_h.abs().max()),
        residual_caveat='Coarse five-seed grid interpolation; actual ten-seed confirmation residuals are retained, not forced to zero.'))
    print(result.to_string(index=False), flush=True)
    print(sentence, flush=True)


def final_cases():
    """Strictly validate the new final families; reuse just-checked E4 acceptance."""
    from assess_v2 import assess
    plan = json.loads((ROOT/'results/plans/final-checks.json').read_text(encoding='utf8'))
    groups = defaultdict(dict)
    for case in plan:
        groups[Path(case['outputDirectory']).name][case['repSeed'], case['scenarioIndex']] = case
    rows = []
    for family, cases in groups.items():
        paths = list((ROOT/'results/native').glob('*/'+family))
        require(len(paths) == 1, f'Missing/ambiguous final native family: {family}')
        warmup = 500 if family.startswith(('e2-', 'e4-')) else 0
        if family.startswith('e4-contrast-'):
            accepted = ROOT/'results/analysis'/family/'acceptance.json'
            data = json.loads(accepted.read_text(encoding='utf8'))
            require(data['runs'] == len(cases) and data['warmup_jobs'] == warmup,
                    f'Invalid preceding E4 acceptance: {family}')
            require({(x['seed'], x['scenario']) for x in data['inputs']} == set(cases),
                    f'Final/E4 native key mismatch: {family}')
            require({p.name for p in paths[0].glob('native-seed-*.log')} == {x['file'] for x in data['inputs']},
                    f'Final/E4 native files differ: {family}')
            rows.append(dict(family=family, runs=len(cases), warmup_jobs=warmup,
                             prior_strict_acceptance_reused=True,
                             acceptance_sha256=hashlib.sha256(accepted.read_bytes()).hexdigest()))
        else:
            frame, _, _ = assess(paths[0], warmup, cases.keys(), cases)
            rows.append(dict(family=family, runs=len(frame), warmup_jobs=warmup,
                             prior_strict_acceptance_reused=False))
        print(f'Final strict acceptance: {family}, {len(cases)} runs', flush=True)
    require(sum(row['runs'] for row in rows) == len(plan) == 245, 'Incomplete final native acceptance')
    save_json(ROOT/'results/analysis/final-checks-acceptance.json',
              dict(label='SYNTHETIC final canonical native checks', runs=245, families=rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--warmup', action='store_true')
    parser.add_argument('--validation', action='store_true')
    parser.add_argument('--manifold', action='store_true')
    parser.add_argument('--final-cases', action='store_true')
    args = parser.parse_args()
    if args.warmup: warmup_sensitivity()
    if args.validation: validation()
    if args.manifold: manifold()
    if args.final_cases: final_cases()
