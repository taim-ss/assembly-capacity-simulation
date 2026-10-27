"""Synthetic fixtures test inference contracts; they are not execution evidence."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'));sys.path.insert(0,str(ROOT/'tools'))
from native.mm1 import mmc_targets,erlang_c,assess_mmc
from native.metrics import windowed_metrics,windowed_matrix,bottleneck_table
from native.costs import windowed_cost_per_lead_hour_saved,windowed_cost_per_station_hour
from native.comparisons import paired_effects
from native_batch import prepare
import native_batch
import plan_experiments as plans
from assess_v2 import primary_replication_count


def test_primary_inference_distinguishes_single_seed_smoke_and_rejects_unpaired_grid():
    smoke=pd.DataFrame(dict(seed=[41,41,41],scenario=[0,2,3]))
    assert primary_replication_count(smoke)==1
    replicated=pd.concat([smoke,smoke.assign(seed=42)],ignore_index=True)
    assert primary_replication_count(replicated)==2
    with pytest.raises(ValueError,match='identical seed sets'):
        primary_replication_count(pd.concat([smoke,pd.DataFrame(dict(seed=[42],scenario=[2]))]))


def test_erlang_c_special_case_and_invalid_stability():
    expected=mmc_targets(1,.5,1.)
    assert expected['mean_lead_h']==2 and expected['mean_queue']==.5
    assert expected['utilization']==.5
    with pytest.raises(ValueError):erlang_c(3,3.,1.)


def test_mmc_checks_coverage_and_precision():
    targets=mmc_targets(3,2.1,1.)
    frame=pd.DataFrame({k:v*(1+np.linspace(-.01,.01,30)) for k,v in targets.items()})
    assert assess_mmc(frame,3,2.1,1.)['accepted']
    assert not assess_mmc(frame*1.2,3,2.1,1.)['accepted']


def test_window_boundary_counts_prior_jobs_in_wip():
    run=dict(key=(1,0),config={**{'cap_'+s:1 for s in ['Kitting','Assembly','Test','Quality','Handover']}},
             done=(2,2,10.,2),orders={0:(0.,7.,7.,0),1:(3.,10.,7.,0)},
             stages={(0,0,0):(0.,0.,7.,7.),(1,0,0):(3.,7.,10.,3.)})
    result=windowed_metrics(run,1,2)
    assert result['windowed_wip']==pytest.approx(11/7)
    assert result['windowed_throughput_per_h']==pytest.approx(1/7)
    assert result['stations'][0]['window_busy_area']==7
    reps,stations=windowed_matrix([run],{(1,0):(1,1,1,1,1)},1,2)
    assert reps.iloc[0].mean_wip==pytest.approx(11/7)
    assert len(stations)==5
    assert bottleneck_table(stations,{0:'Baseline'})[0].iloc[0].bottleneck_call=='Kitting'


def test_preregistered_cost_gate_is_preserved():
    rows=[]
    for seed in range(1,11):
        for scenario,lead in [(0,100.),(2,90.),(3,95.)]:
            rows.append(dict(seed=seed,scenario=scenario,mean_lead_h=lead,p90_lead_h=lead+10,
                mean_wip=lead*.2,throughput_per_h=.2,window_hours=1000.))
    frame=pd.DataFrame(rows);effects=paired_effects(frame)
    costs=windowed_cost_per_lead_hour_saved(frame,effects)
    assert all(c['windowed_lead_savings_ratio'] is None for c in costs)
    assert all(c['descriptive_lead_hours_only_ratio']>0 for c in costs)
    assert windowed_cost_per_station_hour(frame)[0]['added_cost_rate_per_h']==35


def test_native_batch_has_explicit_start_and_zero_based_case_selection(tmp_path,monkeypatch):
    monkeypatch.setattr(native_batch,'ROOT',tmp_path)
    path=prepare('P3V2Test',[dict(repSeed=1),dict(repSeed=2)],ROOT/'model/P3_Assembly_Flow.alp')
    import xml.etree.ElementTree as ET
    exp=ET.parse(path).getroot().find(".//ParamVariationExperiment[Name='Batch']")
    assert exp.findtext('InitialSetupCode')=='run();'
    assert exp.findtext('NumberOfRuns')=='2'
    expressions=[x.findtext('Expression/Code') for x in exp.findall('FreeformParamValue')]
    assert any('index<1 ? 1 : 2' in x for x in expressions)


def test_planned_sample_sizes_and_independent_sensitivity_axes():
    assert len(plans.pilot())==141
    assert len(plans.confirmation())==1230
    assert len(plans.grid())==160
    sensitivity=plans.sensitivity()
    assert len(sensitivity)==720
    assert {x['scenarioIndex'] for x in sensitivity}=={0,2,3}
    assert len(plans.remaining())==2110


def test_cli_exports_windowed_subset_without_requiring_unused_scenarios(tmp_path):
    sys.path.insert(0,str(ROOT/'analysis/python_replica'))
    from model import ScenarioConfig,run_scenario
    from native.cli import main
    inputs=tmp_path/'logs';inputs.mkdir()
    for seed in [1,2]:
        for scenario in [0,2,3]:
            lines=run_scenario(ScenarioConfig(seed,scenario,scenario_orders=20))['log_lines']
            (inputs/f'native-seed-{seed}-scenario-{scenario}-finite.log').write_text('\n'.join(lines),encoding='utf8')
    output=tmp_path/'analysis'
    main(['--input',str(inputs),'--output',str(output),'--target','20','--seeds','1,2',
          '--scenarios','0,2,3','--warmup-jobs','5'])
    assert (output/'windowed_primary.csv').is_file()
    assert (output/'windowed_costs.csv').is_file()
    assert len(pd.read_csv(output/'windowed_replications.csv'))==6
