"""Cross-check every transition counter against actual completed-order timestamps."""
from .parsing import require,close


def validate_transitions(run,target):
    records=run.get('transitions',[])
    require(len(records)==2*target,'Missing/extra release or completion transition records')
    releases=sorted(order[0] for order in run['orders'].values())
    finishes=sorted(order[1] for order in run['orders'].values())
    arrived=departed=0;previous=-1.
    for tag,time,a,d,wip in records:
        require(time>=previous-1e-7,'Transition times are not chronological')
        if tag=='P3_IN':
            require(arrived<target and close(time,releases[arrived]),'Release transition/order mismatch')
            arrived+=1
        else:
            require(departed<target and close(time,finishes[departed]),'Completion transition/order mismatch')
            departed+=1
        require((a,d,wip)==(arrived,departed,arrived-departed),
                'Cumulative transition counters disagree with actual orders')
        require(arrived>=departed,'Completion before release')
        previous=time
    require(arrived==departed==target,'Terminal transition counters do not match target')
