"""Prepare a native AnyLogic Parameter Variation batch from an explicit SYNTHETIC plan.

No simulation is implemented here. Freeform expressions use the native zero-based
setupRootParameters index to select a predeclared row.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def literal(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


def prepare(name, cases, source=None):
    if not name.isalnum() or not name.startswith('P3V2'):
        raise ValueError('Use an alphanumeric P3V2 name')
    source=source or ROOT/'model/P3_Assembly_Flow.alp'
    tree=ET.parse(source);model=tree.getroot().find('Model')
    old=model.findtext('JavaPackageName')
    for e in model.iter():
        if e.text==old:e.text=name.lower()
    model.find('Name').text=name
    main=model.find("ActiveObjectClasses/ActiveObjectClass[Name='Main']")
    parameters={v.findtext('Id'):(v.findtext('Name'),v.findtext('Properties/Type'),
                v.findtext('Properties/DefaultValue/Code'))
                for v in main.findall('Variables/Variable') if v.get('Class')=='Parameter'}
    template=model.find("Experiments/ParamVariationExperiment[Name='FiniteCapacitySweep']")
    batch=copy.deepcopy(template)
    batch.find('Name').text='Batch'
    batch.find('Id').text='1950000000001'
    batch.find('UseFreeformParameters').text='true'
    batch.find('NumberOfRuns').text=str(len(cases))
    ET.SubElement(batch,'BypassInitialScreen').text='true'
    initial=batch.find('InitialSetupCode')
    if initial is None:initial=ET.SubElement(batch,'InitialSetupCode')
    initial.text='run();'
    batch.find('MaximumMemory').text='1024'
    for e in batch.findall('RangeVariationParamValue'):batch.remove(e)
    for e in batch.findall('FreeformParamValue'):batch.remove(e)
    for ident,(key,typ,default) in parameters.items():
        values=[literal(c[key]) if key in c else default for c in cases]
        chunks=[]
        for i,value in enumerate(values):
            if not chunks or chunks[-1][1]!=value:chunks.append([i+1,value])
            else:chunks[-1][0]=i+1
        if len(chunks)==1:expr=values[0]
        elif len(chunks)<=48:
            expr=chunks[-1][1]
            for end,value in reversed(chunks[:-1]):expr=f"(index<{end} ? {value} : {expr})"
        else:expr='new '+typ+'[]{'+','.join(values)+'}[index]'

        node=ET.SubElement(batch,'FreeformParamValue');ET.SubElement(node,'Id').text=ident
        expression=ET.SubElement(node,'Expression',Class='CodeValue')
        ET.SubElement(expression,'Code').text=expr
    model.find('Experiments').append(batch)
    directory=ROOT/'tools/.build/native'/name;directory.mkdir(parents=True,exist_ok=False)
    target=directory/(name+'.alp');tree.write(target,encoding='utf-8',xml_declaration=True)
    manifest=dict(label='SYNTHETIC native AnyLogic batch plan; no simulator fallback',
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  copy_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),cases=cases,
                  experiment='Batch',model=str(target))
    (directory/'batch-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('plan',type=Path)
    a=p.parse_args();print(prepare(a.name,json.loads(a.plan.read_text(encoding='utf8'))))
