"""Sensor-module story, separate 2D dashboard and 3D-only production scene.

All counts read native state. Furniture illustrates assumed sensor manufacture.
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from . import layout as L
from . import primitives as P
from . import scene_props,shipping
from .schema import header,tag,shape_expression

NAVY='#17324d'
MUTED='#526476'
PAPER='#f4f7fb'
STORY={
 'dock':('INCOMING PARTS','Boards, probes and housings'),
 'kitting':('1  KIT PARTS','Match PCB + probe + housing'),
 'assembly':('2  ASSEMBLE','Fit PCB, probe and case'),
 'test':('3  FUNCTIONAL TEST','Check wiring + response'),
 'quality':('4  QUALITY CHECK','Inspect finish and approve'),
 'handover':('5  PACK','Pack + label sensor'),
 'ship':('READY TO SHIP','Completed work orders')}


def _text(name,x,y,text='',*,code=None,size=14,color=NAVY,mode='2d'):
    return P.text_shape('a3d_'+name,x,y,text,color_hex=color,size=size,
                        bold=True,text_code=code,mode=mode,z=5 if mode=='3d' else 0)


def _unit_markers(station):
    if station.pool_var is None:return []
    out=[]
    for i in range(L.MAX_UNITS_PER_STAGE):
        fill=(f'return busy[{station.stage_index}]>{i} ? '
              'new java.awt.Color(35,139,96) : new java.awt.Color(151,164,177);')
        out.append(P.oval3d(f'a3d_unit_{station.key}_{i}',station.x-55+i*22,
            L.STATION_Y+38,8,8,station.color,z=76,z_height=18,
            fill_code=fill,visible_code=f'return {i} < {station.pool_var}.size();',mode='3d'))
    return out


def _queue_lane(station):
    if station.stage_index is None:return []
    y=L.STATION_Y-L.LANE_OFFSET_Y
    width=L.LANE_VISIBLE_SLOTS*L.LANE_SLOT_SPACING+10
    out=[P.rectangle3d(f'a3d_lane_{station.key}',station.x-width//2,y-13,
        width,26,'#e3eaf1',z=68,z_height=3,mode='3d')]
    for i in range(L.LANE_VISIBLE_SLOTS):
        out.append(P.rectangle3d(f'a3d_wait_slot_{station.key}_{i}',
            station.x-(L.LANE_VISIBLE_SLOTS*L.LANE_SLOT_SPACING)//2+i*L.LANE_SLOT_SPACING,
            y-9,18,18,'#f8fafc',z=71,z_height=1,line_hex='#a7b5c3',mode='3d'))
    overflow=(f'{{int n=queued[{station.stage_index}]-{L.LANE_VISIBLE_SLOTS}; '
              'return n>0 ? "+"+n+" MORE WAITING" : "WAITING LANE";}')
    out.append(_text(f'overflow_{station.key}',station.x-85,y-26,
                    code=overflow,size=13,color=MUTED,mode='3d'))
    return out


def _station_group(station):
    heading,detail=STORY[station.key]
    out=[P.rectangle3d(f'a3d_zone_{station.key}',station.x-95,240,190,195,
         '#edf2f7',z=0,z_height=1,line_hex='#bac8d5',mode='3d'),
         P.rectangle3d(f'a3d_zone_band_{station.key}',station.x-95,430,
         190,5,station.color,z=2,z_height=2,mode='3d')]
    out.extend(scene_props.for_station(station))
    out.extend(_unit_markers(station))
    out.extend(_queue_lane(station))
    out.append(_text(f'label_{station.key}',station.x-92,380,heading,size=16,mode='3d'))
    out.append(_text(f'detail_{station.key}',station.x-92,403,detail,size=11,color=MUTED,mode='3d'))
    if station.pool_var is not None:
        out.append(_text(f'capline_{station.key}',station.x-92,422,
            code=f'{{return "RESOURCE UNITS: "+{station.pool_var}.size();}}',size=12,mode='3d'))
    return out


def _flow_paths():
    out=[]
    for left,right in zip(L.STATIONS,L.STATIONS[1:]):
        arrow=P.polyline(f'a3d_forward_{left.key}',
            [(left.x+76,L.STATION_Y),(right.x-76,L.STATION_Y)],
            '#536f87',width=5,dashed=False,mode='3d',z=4)
        out.append(arrow)
    route=P.polyline('a3d_rework_path',
        [(L.TEST_X,L.STATION_Y+55),(L.TEST_X,L.REWORK_LANE_Y),
         (L.ASSEMBLY_X,L.REWORK_LANE_Y),(L.ASSEMBLY_X,L.STATION_Y+55)],
        L.COLOR_REWORK,width=5,dashed=True,mode='3d',z=4)
    out.append(route)
    out.append(_text('rework_label',L.ASSEMBLY_X-35,L.REWORK_LANE_Y+26,
        'FAILED TEST > REPAIR > RETEST',size=14,color=L.COLOR_REWORK,mode='3d'))
    return out


def _story_dashboard():
    out=[P.rectangle3d('a3d_dashboard_bg',0,0,1640,330,PAPER,line_hex=PAPER,mode='2d'),
        _text('title',20,30,'P3 | SENSOR-MODULE ASSEMBLY',size=25),
        _text('story',20,58,'Build industrial temperature sensors: prepare parts, assemble, test, inspect and pack.',size=15,color=MUTED),
        _text('decision',20,85,'DECISION: Where does ONE extra resource cut waiting most - ASSEMBLY or TEST?',size=16),
        _text('synthetic',20,109,'SYNTHETIC learning case | Layout, capacities and processing assumptions are illustrative.',size=12,color='#9c4b1b')]
    scenario=('{String[] names={"BASELINE","KITTING +1","ASSEMBLY +1","TEST +1",'
              '"QUALITY +1","PACKING +1"};return "CURRENT RUN: "+names[scenarioIndex];}')
    out.extend([_text('scenario',1165,30,code=scenario,size=16),
        _text('compare_hint',1165,56,'Same jobs and input draws in each comparison',size=12,color=MUTED),
        _text('motion_note',1165,80,'Travel illustrates flow; it adds no process time.',size=12,color=MUTED),
        _text('kpi_0',1165,105,code='{return String.format("MODEL CLOCK: %.1f h",time());}',size=12)])
    cards=[('RELEASED','""+ordersIn'),('COMPLETED','""+ordersOut'),
           ('IN PROGRESS','""+(ordersIn-ordersOut)'),
           ('MEAN COMPLETION TIME','ordersOut>0 ? String.format("%.1f h",completedLeadSum/ordersOut) : "No completion yet"')]
    for i,(title,expression) in enumerate(cards):
        x=20+i*405
        out.extend([P.rectangle3d(f'a3d_metric_card_{i}',x,127,390,65,
                    '#ffffff',line_hex='#d7e0e9',mode='2d'),
                    _text(f'metric_title_{i}',x+12,148,title,size=11,color=MUTED),
                    _text(f'kpi_{i+1}',x+12,163,code='{return '+expression+';}',size=21)])
    out.append(_text('look_for',20,218,
        'WATCH: orders join the blue waiting lanes; active units turn green; failed tests return on the red route.',size=13,color=MUTED))
    return out


def _station_cards():
    out=[]
    for k,station in L.STAGE_STATIONS.items():
        x=20+k*324
        code=(f'{{return "Capacity "+{station.pool_var}.size()+"  |  Busy "+busy[{k}]+'
              f'"  |  Waiting "+queued[{k}];}}')
        out.extend([P.rectangle3d(f'a3d_station_card_{k}',x,235,308,74,
                    '#ffffff',line_hex='#d7e0e9',mode='2d'),
                    _text(f'card_heading_{k}',x+10,246,STORY[station.key][0],size=13),
                    _text(f'card_values_{k}',x+10,270,code=code,size=12,color=MUTED),
                    P.rectangle3d(f'a3d_queue_chart_bg_{k}',x+10,290,280,7,
                    '#e4eaf1',line_hex='#e4eaf1',mode='2d')])
        bar=P.rectangle3d(f'a3d_queue_chart_bar_{k}',x+10,290,280,7,
                          L.COLOR_WAITING,line_hex=L.COLOR_WAITING,mode='2d')
        shape_expression(bar,'ScaleXCode',f'return Math.min(1.0,queued[{k}]/10.0);')
        out.append(bar)
    out.append(_text('queue_scale',20,325,
        'BLUE = waiting  |  GREEN = working  |  RED = rework  |  GREY = idle resource  |  Queue bars cap at 10; counts remain exact.',size=11,color=MUTED))
    return out


def all_main_shapes():
    out=[P.rectangle3d('a3d_ground',L.GROUND_X,L.GROUND_Y,
          L.GROUND_WIDTH,L.GROUND_HEIGHT,'#f5f7fa',z=-2,z_height=2,mode='3d')]
    for station in L.STATIONS:out.extend(_station_group(station))
    out.extend(shipping.sprites())
    out.extend(_flow_paths());out.extend(_story_dashboard());out.extend(_station_cards())
    out.append(P.camera_3d('a3d_camera',820,1050,z=650,rotation_x=40,rotation_z=270))
    window=ET.Element('Control',Type='Window3D');header(window,'a3d_window3d',0,350)
    for key,value in [('Width',1640),('Height',650),('MakeDefaultViewArea','false'),
                      ('FollowCamera','false'),('NavigationType','limitedToZAboveZero'),
                      ('FarClippingDistance',5000),('Camera','a3d_camera')]:tag(window,key,value)
    out.append(window)
    return out
