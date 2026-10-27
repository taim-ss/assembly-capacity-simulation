#!/usr/bin/env python
"""Idempotent post-processing pass that adds the 3D animation layer to a
generated P3_Assembly_Flow.alp.

Usage:
    python tools/add_3d.py --input model/P3_Assembly_Flow.alp --output model/P3_Assembly_Flow.alp
    python tools/add_3d.py --input X.alp --output Y.alp --check-idempotent

What it does, in order (see tools/model_3d/ for each piece):
  1. Parse the .alp (plain ElementTree, no namespaces in this format).
  2. Strip anything this tool previously inserted (schema.strip_generated),
     so re-running is a true no-op on top of the same input.
  3. Append the 5 contract hook Functions to Main (tools/model_3d/hooks.py).
  4. Append ground + 7 stations + rework path + KPI panel + title banner +
     3D view area + camera to Main's presentation (shapes_main.py).
  5. Append the Job box shape to the Job agent type (job_shape.py).
  6. Clone "Simulation" into a new "Demo3D" SimulationExperiment
     (experiment.py).
  7. If Main has no `animationEnabled` parameter yet (p3-logic has not
     landed the v2 parameters), add a minimal fallback one so the hooks at
     least compile/guard correctly -- logged loudly so it is not missed.
  8. Write the result.

Does NOT touch tools/build_model.py, does NOT edit the "Simulation" or any
ParameterVariation/other existing experiment, does NOT read or write any
block's onEnter/onExit code (that wiring is p3-logic's half of the
contract) -- it only fills the 5 hook function BODIES and adds presentation
objects.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_3d import schema  # noqa: E402
from model_3d import hooks, shapes_main, job_shape, experiment, motion, primitives  # noqa: E402


def _ensure_animation_enabled_parameter(main_aoc: ET.Element) -> bool:
    """Returns True if a fallback parameter was added (i.e. p3-logic has not
    added the real one yet)."""
    for v in main_aoc.iter("Variable"):
        name_el = v.find("Name")
        if name_el is not None and name_el.text == "animationEnabled":
            return False

    variables_container = main_aoc
    # Variables sit as direct <Variable> children of the ActiveObjectClass
    # in this generator's output (see tools/build_model.py: variable()).
    v = ET.Element("Variable", Class="Parameter")
    schema.header(v, "animationEnabled")
    props = schema.tag(v, "Properties", SaveInSnapshot="true", ModificatorType="STATIC")
    schema.tag(props, "Type", "boolean")
    schema.tag(props, "UnitType", "NONE")
    schema.tag(props, "SdArray", "false")
    schema.codeval(props, "DefaultValue", "false")
    editor = schema.tag(props, "ParameterEditor")
    schema.tag(editor, "Id", schema.next_id())
    schema.tag(editor, "EditorContolType", "CHECK_BOX")
    schema.tag(editor, "MinSliderValue", 0)
    schema.tag(editor, "MaxSliderValue", 1)
    schema.tag(editor, "DelimeterType", "NO_DELIMETER")

    # Insert right before EmbeddedObjects, matching where build_model.py
    # places the Main-level EmbeddedObjects container.
    embedded = main_aoc.find("EmbeddedObjects")
    children = list(main_aoc)
    if embedded is not None:
        idx = children.index(embedded)
        main_aoc.insert(idx, v)
    else:
        main_aoc.append(v)
    return True


def run(input_path: Path, output_path: Path) -> dict:
    schema.reset_ids()
    tree = ET.parse(input_path)
    root = tree.getroot()

    removed = schema.strip_generated(root)

    main_aoc = schema.find_active_object_class(root, "Main")
    job_aoc = schema.find_active_object_class(root, "Job")

    # The existing native Model/Frame defines the [Origin] view area. Include
    # dashboard + 3D window rather than focusing only the Window3D rectangle.
    frame=root.find('Model/Frame')
    frame.find('Width').text='1640';frame.find('Height').text='1020'

    # Physically separate editor logic from the 0..1640 presentation workspace.
    objects=main_aoc.findall('EmbeddedObjects/EmbeddedObject')
    if objects and min(float(obj.findtext('X','0')) for obj in objects)<2300:
        for obj in objects:obj.find('X').text=str(float(obj.findtext('X'))+2300)
        for point in main_aoc.findall('Connectors/Connector/Points/Point'):
            point.find('X').text=str(float(point.findtext('X'))+2300)
    for i,item in enumerate(main_aoc.findall('Variables/Variable')):
        if item.findtext('Name','').startswith('a3d_'):continue
        item.find('X').text=str(2330+380*(i//18));item.find('Y').text=str(600+35*(i%18))

    # Keep editor model elements available without covering the runtime dashboard.
    for item in [*main_aoc.findall('Variables/Variable'),*objects,*main_aoc.findall('Connectors/Connector')]:
        flag=item.find('PresentationFlag')
        if flag is not None:flag.text='false'

    fallback_param_added = _ensure_animation_enabled_parameter(main_aoc)
    values={"a3d_queues":("java.util.ArrayList<java.util.ArrayList<Job>>","java.util.stream.IntStream.range(0,5).mapToObj(k->new java.util.ArrayList<Job>()).collect(java.util.stream.Collectors.toCollection(java.util.ArrayList::new))"),
            "a3d_active":("java.util.ArrayList<java.util.ArrayList<Job>>","java.util.stream.IntStream.range(0,5).mapToObj(k->new java.util.ArrayList<Job>()).collect(java.util.stream.Collectors.toCollection(java.util.ArrayList::new))"),
            "a3d_slots":("java.util.HashMap<Job,Integer>","new java.util.HashMap<Job,Integer>()"),
            "a3d_completedLeads":("java.util.ArrayList<Double>","new java.util.ArrayList<Double>()"),
            **motion.shipping_fields(),**motion.main_motion_fields()}
    for name,(typ,expr) in values.items():
        v=ET.SubElement(main_aoc.find("Variables"),"Variable",Class="PlainVariable")
        schema.header(v,name)
        v.find('PresentationFlag').text='false'
        props=schema.tag(v,"Properties",SaveInSnapshot="true",Constant="false",AccessType="public",StaticVariable="false")
        schema.tag(props,"Type",typ);schema.codeval(props,"InitialValue",expr)

    for name,(typ,expr) in motion.job_fields().items():
        v=ET.SubElement(job_aoc.find('Variables'),'Variable',Class='PlainVariable')
        schema.header(v,name);v.find('PresentationFlag').text='false'
        props=schema.tag(v,'Properties',SaveInSnapshot='true',Constant='false',AccessType='public',StaticVariable='false')
        schema.tag(props,'Type',typ);schema.codeval(props,'InitialValue',expr)


    for fn in hooks.build_all():
        name=fn.findtext("Name")
        target=main_aoc.find("Variables/Variable[Name='"+name+"']/Properties/InitialValue/Code")
        if target is None:
            raise ValueError("Missing callable hook: "+name)
        names=[a.findtext("Name") for a in fn.findall("Arguments/Argument")]
        target.text="("+",".join(names)+") -> { "+fn.findtext("Body/Code")+" }"

    main_level_presentation = schema.find_presentation_level(main_aoc)
    for shape in shapes_main.all_main_shapes():
        main_level_presentation.append(shape)
    heading=primitives.text_shape('a3d_editor_logic_title',2300,-70,
        'PROCESS LOGIC | separate from the sensor-module 3D presentation',size=20,bold=True)
    heading.find('PresentationFlag').text='false';main_level_presentation.append(heading)

    job_level_presentation = schema.find_presentation_level(job_aoc)
    job_level_presentation.extend(job_shape.all_job_shapes())

    experiments = root.find(".//Experiments")
    simulation_experiment = None
    for exp in experiments.findall("SimulationExperiment"):
        name_el = exp.find("Name")
        if name_el is not None and name_el.text == "Simulation":
            simulation_experiment = exp
            break
    if simulation_experiment is None:
        raise SystemExit("Could not find the 'Simulation' SimulationExperiment to clone for Demo3D")

    aoc_id = main_aoc.find("Id").text
    demo = experiment.build_demo3d(simulation_experiment, aoc_id)
    experiments.append(demo)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    text = output_path.read_bytes()
    return {
        "removed_previous_elements": removed,
        "fallback_animationEnabled_added": fallback_param_added,
        "output_sha256": hashlib.sha256(text).hexdigest(),
        "output_bytes": len(text),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--check-idempotent", action="store_true",
                     help="run twice (2nd pass on the 1st pass's output) and fail if the hashes differ")
    args = ap.parse_args()

    result1 = run(args.input, args.output)
    print("pass 1:", result1)

    if args.check_idempotent:
        result2 = run(args.output, args.output)
        print("pass 2:", result2)
        if result1["output_sha256"] != result2["output_sha256"]:
            print("IDEMPOTENCE CHECK FAILED: hashes differ between pass 1 and pass 2", file=sys.stderr)
            sys.exit(1)
        if result2["removed_previous_elements"] == 0:
            print("WARNING: pass 2 removed 0 elements -- strip_generated() may not be matching pass 1's output",
                  file=sys.stderr)
        print("idempotence check OK")


if __name__ == "__main__":
    main()
