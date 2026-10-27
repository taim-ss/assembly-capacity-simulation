"""Add Demo3D with explicit native ParameterValue defaults and real-time speed.

Simulation and Parameter Variation experiments remain separate. The native
ParameterValue/Code schema was checked against generated Demo3D Java source.
Final visual framing still requires a native visual run after user design review.
"""
from __future__ import annotations

import copy
import xml.etree.ElementTree as ET

from .schema import EXPERIMENT_MARKER, next_id, tag

REAL_TIME_SCALE_MODEL_HOURS_PER_SECOND = 1.5  # slow enough to follow individual visual transfers


def build_demo3d(simulation_experiment: ET.Element, active_object_class_id: str) -> ET.Element:
    e = ET.Element("SimulationExperiment", ActiveObjectClassId=active_object_class_id)
    tag(e, "Id", next_id())
    tag(e, "Name", EXPERIMENT_MARKER)
    tag(e, "MaximumMemory", 512)
    tag(e, "RandomNumberGenerationType", "fixedSeed")
    tag(e, "CustomGeneratorCode", "new java.util.Random()")
    tag(e, "SeedValue", 1)
    tag(e, "SelectionModeForSimultaneousEvents", "FIFO")
    tag(e, "LoadRootFromSnapshot", "false")
    tag(e, "Presentation")

    params = tag(e, "Parameters")
    src_params = simulation_experiment.find("Parameters")
    seen = set()
    if src_params is not None:
        for p in src_params.findall("Parameter"):
            name_el = p.find("ParameterName")
            if name_el is None:
                continue
            seen.add(name_el.text)
            new_p = tag(params, "Parameter")
            tag(new_p, "ParameterName", name_el.text)
    if "animationEnabled" not in seen:
        new_p = tag(params, "Parameter")
        tag(new_p, "ParameterName", "animationEnabled")

    pres = tag(e, "PresentationProperties")
    tag(pres, "EnableZoomAndPanning", "true")
    tag(pres, "ExecutionMode", "realTimeScaled")
    tag(pres, "RealTimeScale", REAL_TIME_SCALE_MODEL_HOURS_PER_SECOND)
    tag(pres, "Title", "P3 | Sensor-module assembly: Assembly +1 or Test +1? | SYNTHETIC")
    tag(pres, "EnableDeveloperPanel", "true")
    tag(pres, "ShowDeveloperPanelOnStart", "false")

    src_time = simulation_experiment.find("ModelTimeProperties")
    if src_time is not None:
        e.append(copy.deepcopy(src_time))

    tag(e, "BypassInitialScreen", "true")  # show the editor's Run window with the 3D view, not headless
    
    overrides={"replayMode":"false","animationEnabled":"true","scenarioOrders":"80","meanInterarrival":"5.0540201005","capKitting":"2","capAssembly":"5","capTest":"5","capQuality":"3","capHandover":"1","reworkProbability":"0.1"}
    for p in params.findall("Parameter"):
        name=p.findtext("ParameterName")
        if name in overrides:
            value=tag(p,"ParameterValue",Class="CodeValue");tag(value,"Code",overrides[name])
    return e
