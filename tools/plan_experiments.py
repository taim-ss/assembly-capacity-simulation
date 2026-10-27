"""SYNTHETIC predeclared P3 v2 native experiment batches; no simulation fallback."""
import argparse
import hashlib
import json
from pathlib import Path
from native_batch import ROOT, prepare

ARRIVAL=5.0540201005
CAPS=[2,5,5,3,1]
PHASE=""
CAP_NAMES=['capKitting','capAssembly','capTest','capQuality','capHandover']


def cases_for(label,seeds,scenarios=range(6),orders=600,caps=None,**overrides):
    cases=[]
    for seed in seeds:
        for scenario in scenarios:
            c=dict(replayMode=False,repSeed=seed,scenarioIndex=scenario,scenarioOrders=orders,
                   meanInterarrival=ARRIVAL,outputDirectory=(ROOT/'results/native'/PHASE/label).as_posix())
            c.update(zip(CAP_NAMES,caps or CAPS));c.update(overrides);cases.append(c)
    return cases


def pilot():
    cases=cases_for('e0-regression',range(1,11),caps=[1]*5,meanInterarrival=30.)
    cases+=cases_for('e0-replay',[1],[0],195,replayMode=True,meanInterarrival=30.,caps=[1]*5)
    cases+=cases_for('e1-pilot',range(1,11),[0],caps=[50]*5,studyLabel='validation')
    cases+=cases_for('e2-pilot',range(1,11),orders=5000,studyLabel='steady')
    cases+=cases_for('e6-pilot',range(1,11),[0],10000,caps=[3,1,1,1,1],
                     verificationMode=True,verificationServers=3,verificationMeanService=1.,meanInterarrival=1/2.1)
    return cases


def grid():
    cases=[]
    for ca in [4,5,6,8]:
        ct=round(ca*17.673504273504275/20.176153846153845)
        for scale in [.5,.6,.7,.8,.9,1.,1.1,1.2]:
            label=f'e4-grid-c{ca}-t{ct}-s{scale}'
            cases+=cases_for(label,range(1,6),[0],2000,[2,ca,ct,3,1],serviceScale=scale)
    return cases


def sensitivity():
    cases=[]
    levels=[('capacity-low',dict(caps=[1,3,3,2,1])),
            ('capacity-high',dict(caps=[3,8,8,5,2])),
            ('service-half',dict(serviceScale=.5)),('service-threequarter',dict(serviceScale=.75)),
            ('fitted',dict(inputMode=1)),('rework05',dict(reworkProbability=.05)),
            ('rework10',dict(reworkProbability=.1)),
            ('components',dict(componentMode=1,componentMeanInterarrival=ARRIVAL))]
    for name,settings in levels:
        cases+=cases_for('e5-'+name,range(1,31),[0,2,3],600,**settings)
    return cases


def confirmation():
    # Fixed disjoint batches, frozen before launch. Pilot is reported separately.
    cases=cases_for('e2-confirmation',range(11,211),orders=5000,studyLabel='steady')
    cases+=cases_for('e6-confirmation',range(11,41),[0],10000,caps=[3,1,1,1,1],
                     verificationMode=True,verificationServers=3,verificationMeanService=1.,meanInterarrival=1/2.1)
    return cases


def remaining():
    return confirmation()+grid()+sensitivity()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['pilot','grid','sensitivity','confirmation','remaining'])
    p.add_argument('--name',required=True);args=p.parse_args()
    PHASE=args.phase
    cases=globals()[args.phase]()
    out=ROOT/'results/plans';out.mkdir(parents=True,exist_ok=True)
    plan=out/(args.phase+'.json');plan.write_text(json.dumps(cases,indent=2),encoding='utf8')
    print(prepare(args.name,cases))
    print(json.dumps(dict(phase=args.phase,runs=len(cases),sha256=hashlib.sha256(plan.read_bytes()).hexdigest())))
