"""Interpolate four capacity/service points from the frozen native grid. SYNTHETIC."""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import plan_experiments as plan
from native_batch import prepare


def main():
    target=float(pd.read_csv(ROOT/'analysis/calibration/clean_orders.csv').end_to_end_elapsed_h.mean())
    rows=[];curves=[];cases=[]
    plan.PHASE='contrast'
    for ca in [4,5,6,8]:
        ct=round(ca*17.673504273504275/20.176153846153845)
        points=[]
        for scale in [.5,.6,.7,.8,.9,1.,1.1,1.2]:
            directory=ROOT/f'results/analysis/e4-grid-c{ca}-t{ct}-s{scale}'
            frame=pd.read_csv(directory/'replications.csv')
            mean=float(frame.mean_lead_h.mean());points.append((scale,mean))
            curves.append(dict(cap_assembly=ca,cap_test=ct,service_scale=scale,mean_lead_h=mean))
        x,y=np.array(points).T
        if not np.all(np.diff(y)>0) or not y[0]<=target<=y[-1]:
            raise ValueError(f'Nonmonotonic/unbracketed calibration at {ca}: {points}')
        scale=float(np.interp(target,y,x))
        rows.append(dict(cap_assembly=ca,cap_test=ct,service_scale=scale,target_mean_h=target,
                         method='Linear interpolation of five-seed post-W500 native grid means'))
        cases+=plan.cases_for(f'e4-contrast-c{ca}-t{ct}',range(1,11),[0,2,3],2000,
                             [2,ca,ct,3,1],serviceScale=scale)
    output=ROOT/'results/plans'
    pd.DataFrame(rows).to_csv(output/'manifold-points.csv',index=False)
    pd.DataFrame(curves).to_csv(output/'manifold-grid.csv',index=False)
    (output/'contrast.json').write_text(json.dumps(cases,indent=2),encoding='utf8')
    print(prepare('P3V2Contrast01',cases));print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':main()
