"""Final source regression and animated/native-to-replica agreement. SYNTHETIC."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from native.parsing import parse_log,require

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis/python_replica'))
from model import ScenarioConfig,run_scenario


def compare(a,b,fields=('orders','stages','kits')):
    differences={}
    for field in fields:
        require(set(a[field])==set(b[field]),f'Final comparison structure mismatch: {field}')
        differences[field]=max((abs(x-y) for key in a[field] for x,y in zip(a[field][key],b[field][key])),default=0.)
    require(max(differences.values())<=1e-9,f'Final timestamp mismatch: {differences}')
    return dict(seed=a['key'][0],scenario=a['key'][1],max_absolute_error_h=differences,
                first_sha256=a['sha256'],second_sha256=b['sha256'])


def replica_match(path):
    actual=parse_log(path);c=actual['config']
    cfg=ScenarioConfig(c['seed'],c['scenario'],scenario_orders=c['target'],mean_interarrival=c['interarrival'],
      service_scale=c['scale'],joint_bootstrap=c['joint'],rework_probability=c['rework'],
      cap_kitting=c['cap_Kitting'],cap_assembly=c['cap_Assembly'],cap_test=c['cap_Test'],
      cap_quality=c['cap_Quality'],cap_handover=c['cap_Handover'],input_mode=c['inputMode'],
      component_mode=c['componentMode'],component_mean_interarrival=c['componentMeanInterarrival'],max_rework=c['maxRework'])
    with tempfile.TemporaryDirectory() as temporary:
        expected=Path(temporary)/'replica.log'
        expected.write_text('\n'.join(run_scenario(cfg)['log_lines']),encoding='utf8')
        return compare(actual,parse_log(expected))


def main():
    p=argparse.ArgumentParser();p.add_argument('--animation',type=Path);args=p.parse_args()
    out=ROOT/'results/final-native-verification.json'
    if args.animation:
        result=json.loads(out.read_text());result['animation']=replica_match(args.animation)
        result['animation']['label']='Actual full native animated cohort versus deterministic Python tape'
    else:
        groups={}
        for current,reference in [('e0-final-default','pilot/e0-regression'),
                                   ('e2-final-equivalence','remaining/e2-confirmation')]:
            rows=[]
            for path in sorted((ROOT/'results/native/final-checks'/current).glob('native-seed-*.log')):
                rows.append(compare(parse_log(path),parse_log(ROOT/'results/native'/reference/path.name)))
            require(len(rows)==60,f'Expected 60 final regression cases: {current}')
            groups[current]=rows
            print(f'{current}: 60 complete native pairs match',flush=True)
        groups['combined_features']=[replica_match(path) for path in sorted(
            (ROOT/'results/native/final-checks/features-final').glob('native-seed-*.log'))]
        require(len(groups['combined_features'])==3,'Missing combined-feature comparisons')
        result=dict(label='SYNTHETIC final native verification; exact tapes, tolerance1e-9h',
                    tolerance_h=1e-9,passed=True,groups=groups,
                    note='Default regression is transitive through the separately accepted v2-default/v1 regression; E2 compares pre-buffer numerical build with final source.')
    out.write_text(json.dumps(result,indent=2),encoding='utf8');print('Final native agreement passed')


if __name__=='__main__':main()
