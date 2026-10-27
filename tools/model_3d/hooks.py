"""Builds the 5 contract hook functions (animRelease, animStageEnter,
animStageStart, animStageFinish, animDone) as Main-level Java Functions.

Contract (docs/v2-feature-spec.md, "3D animation hook contract"): hooks only
move/colour presentation objects; they must never read or write a logic
variable, draw a random number, or change time. What they ARE allowed to
read (verified against that rule): time() (a clock read, not a logic
variable) and read-only Job fields already set by the real logic
(reworks, jobId) purely to choose a colour/slot -- never written here.

Movement updates presentation target fields for wall-clock interpolation;
shape expressions read those fields and presentation phase/colour state.
There is no MoveTo block, simulated travel delay or added random draw.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from . import layout as L
from .schema import FUNCTION_MARKER, JOB_SHAPE_NAME, header, tag

_STAGE_X = ", ".join(str(L.STAGE_STATIONS[k].x) for k in range(5))
_STAGE_LANE_Y = L.STATION_Y - L.LANE_OFFSET_Y
_STAGE_SERVICE_Y = L.STATION_Y
_DOCK_X = L.STATION_BY_KEY["dock"].x
_SHIP_X = L.STATION_BY_KEY["ship"].x
_SPACING = L.LANE_SLOT_SPACING
_SLOTS = L.LANE_VISIBLE_SLOTS


def _color(hex_code: str) -> str:
    h = hex_code.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"new java.awt.Color({r}, {g}, {b})"


def _function_element(name: str, args: list[tuple[str, str]], return_type: str, body: str) -> ET.Element:
    e = ET.Element("Function")
    header(e, name)
    tag(e, "Access", "PUBLIC")
    arguments = tag(e, "Arguments")
    for arg_name, arg_type in args:
        a = tag(arguments, "Argument")
        tag(a, "Name", arg_name)
        tag(a, "Type", arg_type)
    tag(e, "ReturnType", return_type)
    tag(e, "StaticFunction", "false")
    tag(e, "UseUnits", "false")
    body_el = tag(e, "Body", Class="CodeValue")
    tag(body_el, "Code", body)
    return e


def _stage_const_block() -> str:
    return (
        f"final double[] stageX = {{ {_STAGE_X} }};"
        f" final double laneY = {_STAGE_LANE_Y}, serviceY = {_STAGE_SERVICE_Y};"
    )


def build_all() -> list[ET.Element]:
    guard="if (!animationEnabled) return;"
    const=_stage_const_block()
    release=_function_element("animRelease",[("j","Job")],"void",guard+f"j.a3d_position=()->this.a3d_position.apply(j);j.a3d_route=new double[]{{{_DOCK_X},{L.STATION_Y},{_DOCK_X},{L.STATION_Y}}};j.a3d_startedNs=System.nanoTime();j.a3d_phase=0;j.a3d_state=0;j.a3d_shown=true;")
    enter=_function_element("animStageEnter",[("j","Job"),("stage","int")],"void",guard+const+"java.util.ArrayList<Job> q=this.a3d_queues.get(stage); q.add(j);"+
      f"for(int n=0;n<q.size();n++){{Job box=q.get(n);box.a3d_shown=n<{_SLOTS};double x=stageX[stage]-({_SLOTS}*{_SPACING})/2.0+n*{_SPACING};"+
      f"if(box==j && stage==1 && j.a3d_lastStage==2)this.a3d_moveTo.accept(box,new double[]{{{L.TEST_X},{L.REWORK_LANE_Y},{L.ASSEMBLY_X},{L.REWORK_LANE_Y},x,laneY}});else this.a3d_moveTo.accept(box,new double[]{{x,laneY}});}}"+
      "j.a3d_state=(j.reworks>0 && (stage==1||stage==2))?2:0;")
    start=_function_element("animStageStart",[("j","Job"),("stage","int")],"void",guard+const+"java.util.ArrayList<Job> q=this.a3d_queues.get(stage);q.remove(j);"+
      f"for(int n=0;n<q.size();n++){{Job box=q.get(n);box.a3d_shown=n<{_SLOTS};this.a3d_moveTo.accept(box,new double[]{{stageX[stage]-({_SLOTS}*{_SPACING})/2.0+n*{_SPACING},laneY}});}}"+
      "java.util.ArrayList<Job> active=this.a3d_active.get(stage);int slot=0;boolean taken=true;while(taken){taken=false;for(Job other:active)if(this.a3d_slots.get(other)==slot){taken=true;slot++;break;}}active.add(j);this.a3d_slots.put(j,slot);"+
      f"j.a3d_shown=slot<{L.MAX_UNITS_PER_STAGE};this.a3d_moveTo.accept(j,new double[]{{stageX[stage]-{L.STATION_W}/2.0+35+(slot%3)*35,serviceY-20+(slot/3)*24}});"+
      "j.a3d_state=(j.reworks>0 && (stage==1||stage==2))?2:1;if(stage==1)j.a3d_phase=1;else if(stage==3)j.a3d_phase=2;else if(stage==4)j.a3d_phase=3;")
    finish=_function_element("animStageFinish",[("j","Job"),("stage","int")],"void",guard+"this.a3d_active.get(stage).remove(j);this.a3d_slots.remove(j);j.a3d_lastStage=stage;")
    done=_function_element("animDone",[("j","Job")],"void",guard+"this.a3d_completedLeads.add(time()-j.releaseTime);int slot=(ordersOut-1)%6;double[] from=this.a3d_position.apply(j);"+f"this.a3d_shipRoutes[slot]=new double[]{{from[0],from[1],{_SHIP_X}-40+(slot%3)*38,{L.STATION_Y}-15+(slot/3)*35}};"+"this.a3d_shipStartedNs[slot]=System.nanoTime();this.a3d_shipShown[slot]=true;j.a3d_shown=false;")
    return [release,enter,start,finish,done]
