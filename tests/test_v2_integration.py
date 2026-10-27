"""SYNTHETIC fixtures: contracts that exposed real interrupted-build defects."""
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
sys.path.insert(0,str(ROOT/'analysis/python_replica'))
sys.path.insert(0,str(ROOT/'tools'))
from java_random import JavaRandom
from model import ScenarioConfig,run_scenario
from native.parsing import parse_log
from native.validation import validate_run
from native.intervals import station_integrals,wip_area
from add_3d import run as add_3d


def test_java_rejection_emulates_signed_int_overflow():
    class TapeRandom(JavaRandom):
        def __init__(self):self.draws=iter([(1<<31)-1,1])
        def _next(self,bits):return next(self.draws)
    assert TapeRandom().next_int(195)==1


def test_geometric_rework_schema_and_first_test_chain(tmp_path):
    cfg=ScenarioConfig(11,0,scenario_orders=120,rework_probability=.5)
    result=run_scenario(cfg)
    path=tmp_path/'replica.log';path.write_text('\n'.join(result['log_lines']),encoding='utf8')
    run=parse_log(path)
    assert max(row[3] for row in run['orders'].values())>=2
    row,stations,stages=validate_run(run,target=120,rework=.5)
    assert row['target']==120 and len(stations)==5
    for job in result['jobs']:
        assert job.reworks==job.n_rework_target


def test_station_window_integrals_are_exact_and_include_boundary_jobs():
    run=dict(done=(2,2,10.,2),stages={(0,0,0):(0.,2.,5.,3.),(1,0,0):(3.,5.,9.,4.)},
             orders={0:(0.,5.,5.,0),1:(3.,9.,6.,0)})
    areas=station_integrals(run,[1]*5,4.,8.)
    assert areas[0][0]==4 and areas[0][1]==1 and areas[0][4]==0
    assert wip_area(run,4.,8.)==5


def test_new_starvation_proxy_is_not_one_minus_utilization():
    run=dict(done=(1,1,10.,1),stages={(0,0,0):(0.,8.,9.,1.)})
    areas=station_integrals(run,[1]*5)
    assert areas[1][2]==10  # downstream empty-idle
    assert areas[1][3]==8  # only while upstream has a queue


def test_3d_patch_is_idempotent_without_duplicate_hooks(tmp_path):
    source=ROOT/'model/P3_Assembly_Flow.alp';target=tmp_path/'patched.alp'
    first=add_3d(source,target);second=add_3d(target,target)
    assert first['output_sha256']==second['output_sha256']
    root=ET.parse(target).getroot()
    assert len(root.findall(".//SimulationExperiment[Name='Demo3D']"))==1
    assert len(root.findall(".//Control[@Type='Window3D']"))==1
    assert not root.findall('.//Function')
    assert root.find(".//Variable[Name='animStageStart']/Properties/InitialValue/Code") is not None


def test_dynamic_shape_values_use_native_expression_strings():
    root=ET.parse(ROOT/'model/P3_Assembly_Flow.alp').getroot()
    text=root.find(".//Text[Name='a3d_kpi_0']/TextCode")
    visible=root.find(".//Oval[Name='a3d_unit_kitting_0']/VisibleCode")
    scale=root.find(".//Rectangle[Name='a3d_queue_chart_bar_0']/ScaleXCode")
    assert all(node is not None and node.text and not list(node) for node in [text,visible,scale])
    assert 'time()' in text.text and 'kittingPool.size()' in visible.text


def test_animation_patch_preserves_user_functions(tmp_path):
    source=tmp_path/'user-model.alp';target=tmp_path/'patched.alp'
    tree=ET.parse(ROOT/'model/P3_Assembly_Flow.alp')
    main=tree.getroot().find(".//ActiveObjectClass[Name='Main']")
    functions=ET.SubElement(main,'Functions')
    function=ET.SubElement(functions,'Function');ET.SubElement(function,'Name').text='calculateMyKPI'
    ET.SubElement(function,'Body').text='return 42;'
    tree.write(source,encoding='utf8')
    add_3d(source,target)
    assert ET.parse(target).find(".//Function[Name='calculateMyKPI']/Body").text=='return 42;'


def test_both_independent_combine_inputs_have_unlimited_buffers():
    root=ET.parse(ROOT/'model/P3_Assembly_Flow.alp').getroot()
    for name in ['componentBuffer','orderBuffer']:
        block=root.find(f".//EmbeddedObject[Name='{name}']")
        assert block.findtext('ActiveObjectClass/ClassName')=='Queue'
        assert block.findtext("Parameters/Parameter[Name='maximumCapacity']/Value/Code")=='true'


@pytest.mark.parametrize('mutation',['zeros','missing','wrong_time'])
def test_transition_conservation_cannot_be_forged(tmp_path,mutation):
    lines=run_scenario(ScenarioConfig(1,0,scenario_orders=20))['log_lines']
    for index,line in enumerate(lines):
        if not line.startswith(('P3_IN,','P3_STATE,')):continue
        if mutation=='zeros':lines[index]=line.split(',')[0]+','+line.split(',')[1]+',0,0,0'
        elif mutation=='missing':lines.pop(index);break
        else:
            values=line.split(',');values[1]=str(float(values[1])+1);lines[index]=','.join(values);break
    path=tmp_path/'corrupted.log';path.write_text('\n'.join(lines),encoding='utf8')
    with pytest.raises(ValueError):validate_run(parse_log(path),target=20)


@pytest.mark.parametrize('settings',[dict(mean_interarrival=float('nan')),dict(cap_test=0),
                                      dict(rework_probability=.6),dict(component_mode=2)])
def test_replica_rejects_invalid_boundary_configuration(settings):
    with pytest.raises(ValueError):ScenarioConfig(1,0,**settings)
