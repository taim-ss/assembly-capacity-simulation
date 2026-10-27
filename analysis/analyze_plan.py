"""Validate every completed native case against the saved SYNTHETIC batch plan."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from assess_v2 import assess,ROOT


def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--warmup-jobs',type=int,default=0)
    args=p.parse_args();cases=json.loads(args.plan.read_text(encoding='utf8'))
    groups=defaultdict(dict)
    for case in cases:
        family=Path(case['outputDirectory']).name
        groups[family][case['repSeed'],case['scenarioIndex']]=case
    results=[]
    for family,settings in groups.items():
        matches=list((ROOT/'results/native').glob('*/'+family))
        if len(matches)!=1:raise ValueError(f'Expected one native family {family}, found {matches}')
        warmup=args.warmup_jobs if family.startswith(('e2-','e4-','e5-')) else 0
        frame,_,_=assess(matches[0],warmup,settings.keys(),settings)
        results.append(dict(family=family,runs=len(frame),warmup_jobs=warmup))
        print(f'Validated {family}: {len(frame)} actual native runs',flush=True)
    out=ROOT/'results/analysis';out.mkdir(parents=True,exist_ok=True)
    (out/(args.plan.stem+'-acceptance.json')).write_text(json.dumps(results,indent=2),encoding='utf8')


if __name__=='__main__':main()
