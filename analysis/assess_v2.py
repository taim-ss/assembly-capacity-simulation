"""Stream strict validation of SYNTHETIC P3 native experiment families into review tables."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from native.parsing import parse_log,STAGES,require
from native.validation import validate_run,validate_replay_source,scenario_capacities
from native.metrics import windowed_metrics,confidence,bottleneck_table
from native.comparisons import summarize,paired_effects,primary_contrast
from native.costs import windowed_cost_per_lead_hour_saved
from native.mm1 import assess_mmc

ROOT=Path(__file__).resolve().parents[1]


def primary_replication_count(frame):
    """Require complete pairs; a one-seed smoke check has no inferential CI."""
    seeds=[set(frame.loc[frame.scenario==scenario,'seed']) for scenario in (0,2,3)]
    require(seeds[0]==seeds[1]==seeds[2], 'Primary scenarios require identical seed sets')
    return len(seeds[0])


def assess(directory,warmup=0,expected=None,cases=None):
    reps=[];station_rows=[];stage_rows=[];input_hashes=[];keys=[];tapes={}
    for path in sorted(directory.glob('native-seed-*.log')):
        run=parse_log(path);c=run['config'];mode=run['verification'] or ('replay' if c['replay'] else 'finite')
        caps=tuple(c['cap_'+s] for s in STAGES)
        if cases is not None:
            planned=cases.get(run['key']);require(planned is not None,'Unexpected native case')
            mapping={'repSeed':'seed','scenarioIndex':'scenario','scenarioOrders':'target','meanInterarrival':'interarrival','serviceScale':'scale','replayMode':'replay','reworkProbability':'rework','inputMode':'inputMode','componentMode':'componentMode','componentMeanInterarrival':'componentMeanInterarrival','maxRework':'maxRework',**{'cap'+s:'cap_'+s for s in STAGES}}
            defaults=dict(serviceScale=1.,reworkProbability=0.,inputMode=0,componentMode=0,componentMeanInterarrival=5.,maxRework=5)
            for key,field in mapping.items():
                value=planned.get(key,defaults.get(key))
                if value is not None:require(c[field]==value or (isinstance(value,(int,float)) and abs(c[field]-value)<1e-10),f'Plan/config mismatch {key}: {c[field]} vs {value}')

        row,stations,stages=validate_run(run,mode,c['target'],c['interarrival'],c['scale'],caps,c['rework'],c['inputMode'],c['componentMode'],c['componentMeanInterarrival'],c['maxRework'],caps[0])
        keys.append(run['key'])
        # Hash every release and first-visit service, rather than only the first five draws.
        seed,scenario=run['key']
        raw=[(run['orders'][j][0],*[run['stages'][(j,k,0)][3] for k in range(5)]) for j in range(c['target'])]
        tape=np.array(raw,dtype=float)
        if seed in tapes:require(np.max(np.abs(tape-tapes[seed]))<=1e-9,f'Full-job CRN mismatch seed {seed}')
        else:tapes[seed]=tape
        if mode=='replay':validate_replay_source([run],ROOT/'analysis/calibration/clean_orders.csv')
        if warmup:
            window=windowed_metrics(run,warmup,c['target'])
            row.update(mean_lead_h=window['windowed_mean_lead_h'],p90_lead_h=window['windowed_p90_lead_h'],mean_wip=window['windowed_wip'],throughput_per_h=window['windowed_throughput_per_h'],window_hours=window['window_hours'])
            stations=[]
            for k,s in enumerate(window['stations']):
                cap=scenario_capacities(caps,scenario)[k]
                stations.append(dict(seed=seed,scenario=scenario,stage=STAGES[k],capacity=cap,
                    utilization=s['window_busy_area']/(cap*s['window_hours']),mean_queue=s['window_queue_area']/s['window_hours'],
                    starved_by_upstream_fraction=s['window_starved_area']/s['window_hours'],idle_units_mean=s['window_idle_units_area']/s['window_hours']))
        for k,s in enumerate(stages):
            elapsed=[f-e for (j,st,v),(e,b,f,d) in run['stages'].items() if st==k]
            s.update(mean_elapsed_h=float(np.mean(elapsed)),p90_elapsed_h=float(np.quantile(elapsed,.9)))
        reps.append(row);station_rows.extend(stations);stage_rows.extend(stages)
        input_hashes.append(dict(file=path.name,sha256=run['sha256'],seed=seed,scenario=scenario))
    require(keys and len(keys)==len(set(keys)),'Missing or duplicated native evidence')
    if expected is not None:require(set(keys)==set(expected),f'Unexpected native seed/scenario grid in {directory.name}')
    frame=pd.DataFrame(reps);stations=pd.DataFrame(station_rows);stages=pd.DataFrame(stage_rows)
    output=ROOT/'results/analysis'/directory.name;output.mkdir(parents=True,exist_ok=True)
    summary,effects=summarize(frame)
    for name,data in [('replications',frame),('stations',stations),('stages',stages),('summary',summary),('effects',effects)]:data.to_csv(output/(name+'.csv'),index=False)
    paired_n=primary_replication_count(frame) if {0,2,3}.issubset(set(frame.scenario)) else 0
    if paired_n > 1:
        primary_contrast(frame).to_csv(output/'primary.csv',index=False)
        paired_effects(frame).to_csv(output/'paired_effects.csv',index=False)
        if warmup:pd.DataFrame(windowed_cost_per_lead_hour_saved(frame,paired_effects(frame))).to_csv(output/'costs.csv',index=False)
        if not stations.empty:bottleneck_table(stations,{0:'Baseline',2:'Assembly +1',3:'Test +1'})[0].to_csv(output/'bottleneck.csv',index=False)
    result=dict(label='SYNTHETIC actual AnyLogic native results',family=directory.name,runs=len(frame),
                warmup_jobs=warmup,full_job_crn_checked=True,inputs=input_hashes)
    if paired_n==1:
        result['inference']='Not estimated: one matched seed is a strict smoke check, not a replicated confidence interval.'
    if mode=='mmc':result['mmc']=assess_mmc(frame,3,2.1,1.)
    (output/'acceptance.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf8')
    return frame,stations,stages


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--warmup-jobs',type=int,default=0)
    args=p.parse_args();frame,_,_=assess(args.directory,args.warmup_jobs)
    print(frame.groupby('scenario').mean_lead_h.agg(['count','mean']).to_string())
