"""Compare full native v2 visit/kit/order tapes with the Python replica. SYNTHETIC."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis/python_replica'))
from model import ScenarioConfig,run_scenario
from native.parsing import parse_log


def compare(plan,seeds=10):
    mapping=dict(repSeed='rep_seed',scenarioIndex='scenario_index',scenarioOrders='scenario_orders',
                 meanInterarrival='mean_interarrival',serviceScale='service_scale',
                 reworkProbability='rework_probability',capKitting='cap_kitting',
                 capAssembly='cap_assembly',capTest='cap_test',capQuality='cap_quality',
                 capHandover='cap_handover',inputMode='input_mode',componentMode='component_mode',
                 componentMeanInterarrival='component_mean_interarrival',maxRework='max_rework')
    families=('e5-fitted','e5-rework05','e5-rework10','e5-components')
    rows=[]
    with tempfile.TemporaryDirectory() as directory:
        replica_path=Path(directory)/'replica.log'
        for c in plan:
            family=Path(c['outputDirectory']).name
            if family not in families or c['repSeed']>seeds:continue
            paths=list((ROOT/'results/native').glob(f'*/{family}/native-seed-{c["repSeed"]}-scenario-{c["scenarioIndex"]}-finite.log'))
            if len(paths)!=1:raise ValueError(f'Native evidence missing/ambiguous: {family} {c["repSeed"]}')
            native=parse_log(paths[0])
            cfg=ScenarioConfig(**{v:c[k] for k,v in mapping.items() if k in c})
            replica_path.write_text('\n'.join(run_scenario(cfg)['log_lines']),encoding='utf8')
            replica=parse_log(replica_path)
            differences={};structure=True
            for field in ('orders','stages','kits'):
                a,b=native[field],replica[field]
                if set(a)!=set(b):structure=False;differences[field]=None;continue
                differences[field]=max((abs(x-y) for key in a for x,y in zip(a[key],b[key])),default=0.)
            passed=structure and all(v is not None and v<=1e-9 for v in differences.values())
            rows.append(dict(family=family,seed=c['repSeed'],scenario=c['scenarioIndex'],
                             native_sha256=native['sha256'],structure_matches=structure,
                             max_abs_difference_h=differences,passed=passed))
            print(f'{family} seed{c["repSeed"]} scenario{c["scenarioIndex"]}: {differences}',flush=True)
    if len(rows)!=len(families)*seeds*3:raise ValueError('Incomplete planned comparison matrix')
    return dict(label='SYNTHETIC deterministic-tape agreement; actual native vs Python replica',
                tolerance_h=1e-9,runs=len(rows),passed=all(r['passed'] for r in rows),comparisons=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--seeds',type=int,default=10)
    args=p.parse_args();result=compare(json.loads(args.plan.read_text()),args.seeds)
    (ROOT/'results/replica-v2-agreement.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='comparisons'}))
    if not result['passed']:raise SystemExit(1)
