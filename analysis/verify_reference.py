"""Stream v1 actual native logs through the v2 strict analyzer, without modifying v1."""
import json
from pathlib import Path
import pandas as pd
from native.parsing import parse_log
from native.validation import validate_run
from native.comparisons import summarize,primary_contrast

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT.parent/'p3-assembly-flow/results/native/confirmation'
    rows=[];stations=[]
    for path in sorted(source.glob('native-seed-*-scenario-*-finite.log')):
        run=parse_log(path);row,station,_=validate_run(run)
        rows.append(row);stations.extend(station)
    frame=pd.DataFrame(rows)
    assert len(frame)==1140 and set(frame.seed)==set(range(11,201))
    assert set(zip(frame.seed,frame.scenario))=={(s,c) for s in range(11,201) for c in range(6)}
    summary,effects=summarize(frame);direct=primary_contrast(frame)
    out=ROOT/'results/v1-reproduction';out.mkdir(parents=True,exist_ok=True)
    for name,data in [('replications',frame),('summary',summary),('paired',effects),('primary',direct),('stations',pd.DataFrame(stations))]:data.to_csv(out/(name+'.csv'),index=False)
    result=dict(label='SYNTHETIC actual v1 AnyLogic logs independently reanalyzed with v2 analyzer',runs=len(frame),
      baseline_mean_h=float(frame[frame.scenario==0].mean_lead_h.mean()),
      assembly_saves_h=float(effects[(effects.scenario==2)&(effects.metric=='mean_lead_h')]['mean'].iloc[0]),
      test_saves_h=float(effects[(effects.scenario==3)&(effects.metric=='mean_lead_h')]['mean'].iloc[0]),
      direct=json.loads(direct.to_json(orient='records')))
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
