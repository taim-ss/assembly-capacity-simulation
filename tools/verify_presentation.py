"""Compare process contracts across a presentation-only change. No simulation."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def process_contract(path):
    model=ET.parse(path).getroot().find('Model');agents={}
    for agent in model.findall('ActiveObjectClasses/ActiveObjectClass'):
        variables={}
        for v in agent.findall('Variables/Variable'):
            name=v.findtext('Name')
            if name.startswith(('a3d_','anim')):continue
            variables[name]=ET.tostring(v.find('Properties'),encoding='unicode')
        blocks={}
        for b in agent.findall('EmbeddedObjects/EmbeddedObject'):
            blocks[b.findtext('Name')]=dict(typ=b.findtext('ActiveObjectClass/ClassName'),
                parameters=ET.tostring(b.find('Parameters'),encoding='unicode'))
        connections=[]
        for c in agent.findall('Connectors/Connector'):
            connections.append(tuple(c.findtext(key) for key in [
                'SourceEmbeddedObjectReference/ItemName','SourceConnectableItemReference/ItemName',
                'TargetEmbeddedObjectReference/ItemName','TargetConnectableItemReference/ItemName']))
        agents[agent.findtext('Name')]=dict(variables=variables,blocks=blocks,connections=connections)
    experiments={e.findtext('Name'):ET.tostring(e,encoding='unicode')
                 for e in model.findall('Experiments/*') if e.findtext('Name')!='Demo3D'}
    return dict(agents=agents,experiments=experiments,units=model.findtext('ModelTimeUnit'))


def main():
    p=argparse.ArgumentParser();p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    args=p.parse_args();a,b=process_contract(args.before),process_contract(args.after)
    result=dict(label='SYNTHETIC presentation-only process-contract comparison; not native execution',
       before_sha256=hashlib.sha256(args.before.read_bytes()).hexdigest(),
       after_sha256=hashlib.sha256(args.after.read_bytes()).hexdigest(),
       process_contract_unchanged=a==b,
       scope='All non-presentation variables, PML parameter expressions/callbacks, connections, units and non-Demo3D experiments')
    (ROOT/'results/presentation-contract.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))
    if a!=b:raise SystemExit(1)


if __name__=='__main__':main()
