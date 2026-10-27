"""Exact time integrals reconstructed from SYNTHETIC native stage timestamps.

No interpolation between sink snapshots. Equal-time state changes are combined;
zero-duration transient states have zero weight. Buffers are unlimited.
"""
from collections import defaultdict


def station_integrals(run, capacities, start=0.0, end=None):
    end=run['done'][2] if end is None else end
    events=defaultdict(lambda: [0]*10)
    for (job,stage,visit),(entered,started,finished,duration) in run['stages'].items():
        events[entered][5+stage]+=1
        events[started][5+stage]-=1
        events[started][stage]+=1
        events[finished][stage]-=1
    state=[0]*10;areas=[[0.0]*5 for _ in range(5)];previous=0.0
    for time,delta in sorted(events.items())+[(end,[0]*10)]:
        if time> end:time=end
        dt=max(0.0,min(time,end)-max(previous,start))
        for k,cap in enumerate(capacities):
            busy,queue=state[k],state[5+k]
            areas[k][0]+=dt*busy;areas[k][1]+=dt*queue
            areas[k][2]+=dt*(busy==0 and queue==0)
            areas[k][3]+=dt*(busy==0 and queue==0 and k>0 and state[5+k-1]>0)
            areas[k][4]+=dt*(cap-busy)
        state=[a+b for a,b in zip(state,delta)];previous=time
        if time>=end:break
    return areas


def wip_area(run,start,end):
    return sum(max(0.0,min(finish,end)-max(release,start))
               for release,finish,lead,reworks in run['orders'].values())
