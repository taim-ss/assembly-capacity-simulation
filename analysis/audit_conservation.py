"""Audit transition counters in all actual P3 v2 native logs, without loading stages."""
import json
from pathlib import Path
from native.conservation import validate_transitions

ROOT=Path(__file__).resolve().parents[1]


def main():
    files=sorted((ROOT/'results/native').rglob('native-seed-*.log'));passed=[]
    for path in files:
        run=dict(orders={},transitions=[]);target=None;done=False
        for line in path.open(encoding='utf8'):
            if not line.startswith(('P3_IN,','P3_STATE,','P3_ORDER,','P3_CONFIG,','P3_DONE,')):continue
            tag,*v=line.strip().split(',')
            if tag=='P3_CONFIG':target=int(v[3])
            elif tag=='P3_ORDER':run['orders'][int(v[2])]=tuple(map(float,v[3:7]))
            elif tag=='P3_DONE':done=True
            else:run['transitions'].append((tag,float(v[0]),*map(int,v[1:])))
        if not done:raise ValueError(f'Incomplete native evidence: {path}')
        validate_transitions(run,target);passed.append(str(path.relative_to(ROOT)))
        if len(passed)%100==0:print(f'Conservation audit: {len(passed)}/{len(files)}',flush=True)
    output=dict(label='SYNTHETIC actual native per-transition conservation audit',passed=True,
                runs=len(passed),files=passed)
    (ROOT/'results/conservation-audit.json').write_text(json.dumps(output,indent=2),encoding='utf8')
    print(f'Passed {len(passed)} actual native logs')


if __name__=='__main__':main()
