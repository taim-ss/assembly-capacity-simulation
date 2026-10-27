"""Prepare an isolated native Demo3D copy; overrides are recorded, no rendering substitute."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from native_batch import ROOT,prepare


def main():
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--speed',type=float,default=2.)
    p.add_argument('--source',type=Path);args=p.parse_args()
    target=prepare(args.name,[{}],args.source)
    tree=ET.parse(target);model=tree.getroot().find('Model')
    experiment=model.find("Experiments/SimulationExperiment[Name='Demo3D']")
    directory=ROOT/'results/native-3d'/args.name
    for item in experiment.findall('Parameters/Parameter'):
        if item.findtext('ParameterName')=='outputDirectory':
            for child in item.findall('ParameterValue'):item.remove(child)
            value=ET.SubElement(item,'ParameterValue',Class='CodeValue')
            ET.SubElement(value,'Code').text=json.dumps((directory/'runtime').as_posix())
    experiment.find('PresentationProperties/RealTimeScale').text=str(args.speed)
    tree.write(target,encoding='utf8',xml_declaration=True)
    directory.mkdir(parents=True,exist_ok=False)
    manifest=dict(source_sha256=hashlib.sha256((args.source or ROOT/'model/P3_Assembly_Flow.alp').read_bytes()).hexdigest(),
                  copy_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),model=str(target),
                  experiment='Demo3D',speed_model_hours_per_second=args.speed,
                  label='SYNTHETIC actual native visual run; presentation speed/output/name overrides only')
    (directory/'visual-plan.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(target)


if __name__=='__main__':main()
