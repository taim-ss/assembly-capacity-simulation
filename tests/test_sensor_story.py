"""Sensor story contracts: separation, process preservation and actual Java travel code."""
import subprocess
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from model_3d.motion import job_fields,main_motion_fields
from verify_presentation import process_contract


def test_editor_flowchart_and_runtime_scene_are_separate():
    model=ET.parse(ROOT/'model/P3_Assembly_Flow.alp').getroot().find('Model')
    main=model.find("ActiveObjectClasses/ActiveObjectClass[Name='Main']")
    objects=main.findall('EmbeddedObjects/EmbeddedObject')
    assert min(float(b.findtext('X')) for b in objects)>=2300
    assert all(b.findtext('PresentationFlag')=='false' for b in objects)
    for p in main.findall('Connectors/Connector/Points/Point'):assert float(p.findtext('X'))>=2300
    assert all(c.findtext('PresentationFlag')=='false' for c in main.findall('Connectors/Connector'))
    window=main.find(".//Control[Name='a3d_window3d']")
    assert window.findtext('Y')=='350' and window.findtext('MakeDefaultViewArea')=='false'
    assert int(model.findtext('Frame/Height'))>=int(window.findtext('Y'))+int(window.findtext('Height'))
    for e in main.findall('Presentation/Level/Presentation/*'):
        n=e.findtext('Name','')
        if n.startswith(('a3d_prop_','a3d_forward_','a3d_zone_','a3d_lane_')):
            assert e.findtext('DrawMode')=='SHAPE_DRAW_3D'


def test_sensor_appearance_and_rework_route_are_present():
    model=ET.parse(ROOT/'model/P3_Assembly_Flow.alp').getroot()
    job=model.find(".//ActiveObjectClass[Name='Job']")
    for name in ['pcb','housing','sensing_tip','qa_seal','carton']:
        shape=job.find(f".//Presentation/*[Name='a3d_product_{name}']")
        assert shape is not None and shape.find('XCode') is not None
    body=model.findtext(".//Variable[Name='animStageEnter']/Properties/InitialValue/Code")
    assert 'a3d_lastStage==2' in body and '470' in body
    for name in ['animStageEnter','animStageStart']:
        text=model.findtext(f".//Variable[Name='{name}']/Properties/InitialValue/Code")
        assert 'a3d_moveTo.accept' in text
        assert not any(token in text for token in ['nextDouble','schedule(','setStopTime','moveTo('])


def test_products_fit_slots_and_sink_completion_uses_persistent_sprites():
    root=ET.parse(ROOT/'model/P3_Assembly_Flow.alp').getroot()
    box=root.find(".//ActiveObjectClass[Name='Job']//Rectangle[Name='a3d_box']")
    assert float(box.findtext('Width'))<22 and float(box.findtext('Height'))<24
    done=root.findtext(".//Variable[Name='animDone']/Properties/InitialValue/Code")
    assert 'a3d_shipRoutes[slot]' in done and 'a3d_shipShown[slot]=true' in done
    assert 'a3d_shipSlots' not in done and 'j.a3d_moveTo' not in done
    main=root.find(".//ActiveObjectClass[Name='Main']")
    assert len(main.findall(".//Rectangle[Name='a3d_shipping_0_carton']"))==1
    assert not root.findall(".//Variable[Name='a3d_shipSlots']")


def test_actual_java_motion_follows_bend_and_preserves_rework_endpoint(tmp_path):
    install=Path('C:/Program Files/AnyLogic 8.9 Personal Learning Edition/jre/bin')
    if not (install/'javac.exe').exists():pytest.skip('Local Java compiler not installed')
    fields='\n'.join(f'{typ} {name}={expr};' for name,(typ,expr) in job_fields().items() if name!='a3d_owner')
    helpers='\n'.join(f'{typ} {name}={expr};' for name,(typ,expr) in main_motion_fields().items())
    code='public class MotionProbe{static class Job{'+fields+'}'+helpers+'''public static void main(String[] args){
      MotionProbe p=new MotionProbe();Job j=new Job();j.a3d_route=new double[]{0,0,10,0,10,10};
      j.a3d_startedNs=System.nanoTime()-400000000L;double[] v=p.a3d_position.apply(j);
      if(Math.abs(v[0]-10)>.1 || Math.abs(v[1])>.1)throw new AssertionError("bend");
      long start=j.a3d_startedNs;p.a3d_moveTo.accept(j,new double[]{20,20});
      if(j.a3d_route.length!=6 || j.a3d_route[2]!=10 || j.a3d_startedNs!=start)throw new AssertionError("route lost");
      j.a3d_startedNs=System.nanoTime()-1600000000L;v=p.a3d_position.apply(j);
      if(v[0]!=20 || v[1]!=20)throw new AssertionError("end point");
      p.a3d_moveTo.accept(j,new double[]{30,30});
      if(j.a3d_route[0]!=20 || j.a3d_route[1]!=20)throw new AssertionError("continuity");
      System.out.println("MOTION_PROBE_PASS");}}'''
    source=tmp_path/'MotionProbe.java';source.write_text(code,encoding='utf8')
    subprocess.run([str(install/'javac.exe'),'-encoding','UTF-8',str(source)],check=True,capture_output=True)
    result=subprocess.run([str(install/'java.exe'),'-cp',str(tmp_path),'MotionProbe'],check=True,capture_output=True,text=True)
    assert 'MOTION_PROBE_PASS' in result.stdout
