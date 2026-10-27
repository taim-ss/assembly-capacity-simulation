"""Low-level XML helpers for editing the generated .alp with ElementTree.

Every element add_3d.py creates carries a Name (or Id, for experiments) that
starts with one of the MARKER prefixes below, and every Id comes from a
fixed, dedicated range (ID_BASE..) that tools/build_model.py never reaches.
That makes the whole pass idempotent: strip_generated() deletes anything
carrying a marker, then the builders recreate the identical elements in the
identical order, so running add_3d.py twice on its own output yields byte
-identical XML.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterable, Optional

SHAPE_MARKER = "a3d_"          # presentation shapes this tool owns
FUNCTION_MARKER = "anim"        # the 5 contract hook functions + helpers
EXPERIMENT_MARKER = "Demo3D"    # the 3D demo experiment
JOB_SHAPE_NAME = "a3d_box"      # the 3D box added to the Job agent type

ID_BASE = 1_900_000_000_000     # dedicated range, never used by build_model.py
_counter = {"next": ID_BASE}


def reset_ids() -> None:
    _counter["next"] = ID_BASE


def next_id() -> int:
    _counter["next"] += 1
    return _counter["next"]


def tag(parent: ET.Element, name: str, value: Optional[object] = None, **attrs: str) -> ET.Element:
    e = ET.SubElement(parent, name, attrs)
    if value is not None:
        e.text = str(value)
    return e


def codeval(parent: ET.Element, name: str, code_text: str, classname: str = "CodeValue") -> ET.Element:
    e = tag(parent, name, Class=classname)
    tag(e, "Code", code_text)
    return e


def shape_expression(parent: ET.Element, name: str, source: str) -> ET.Element:
    """OM shape dynamic properties are Java-expression strings, not CodeValue beans."""
    body=source.strip()
    if body.startswith('{') and body.endswith('}'):body=body[1:-1].strip()
    if body.startswith('return ') and body.count(';')==1:
        expression=body[7:-1].strip()
    else:
        typ='String' if name=='TextCode' else ('java.awt.Color' if name=='FillColorCode' else 'Double')
        expression=f'((java.util.function.Supplier<{typ}>)()->{{{body}}}).get()'
    return tag(parent,name,expression)


def header(e: ET.Element, name: str, x: int = 0, y: int = 0) -> ET.Element:
    """Id/Name/X/Y/Label/flags header shared by every EmbeddedObject-like and
    OMAbstractAnimationLayerElement-derived element (Text, Rectangle, Oval,
    Group, ViewArea, Camera3D all inherit it)."""
    tag(e, "Id", next_id())
    tag(e, "Name", name)
    tag(e, "X", x)
    tag(e, "Y", y)
    label = tag(e, "Label")
    tag(label, "X", 0)
    tag(label, "Y", -20)
    tag(e, "PublicFlag", "false")
    tag(e, "PresentationFlag", "true")
    tag(e, "ShowLabel", "false")
    return e


def find_active_object_class(root: ET.Element, name: str) -> ET.Element:
    for e in root.iter("ActiveObjectClass"):
        n = e.find("Name")
        if n is not None and n.text == name:
            return e
    raise ValueError(f"ActiveObjectClass '{name}' not found")


def find_presentation_level(aoc: ET.Element) -> ET.Element:
    """Return the <Presentation> element of the agent's single <Level>
    (verified structure: ActiveObjectClass/.../Presentation/Level/Presentation)."""
    top_presentation = aoc.find("Presentation")
    level = top_presentation.find("Level")
    level_presentation = level.find("Presentation")
    if level_presentation is None:
        level_presentation = ET.SubElement(level, "Presentation")
    return level_presentation


def find_embedded_objects(aoc: ET.Element) -> ET.Element:
    e = aoc.find("EmbeddedObjects")
    if e is None:
        e = ET.SubElement(aoc, "EmbeddedObjects")
    return e


def find_experiments(root: ET.Element) -> ET.Element:
    for frame in root.iter():
        pass
    exps = root.find(".//Experiments")
    if exps is None:
        raise ValueError("<Experiments> container not found")
    return exps


def _is_ours(e: ET.Element) -> bool:
    name_el = e.find("Name")
    name = name_el.text if name_el is not None else None
    return bool(name) and (name.startswith(SHAPE_MARKER) or name.startswith(FUNCTION_MARKER))


def strip_generated(root: ET.Element) -> int:
    """Remove every element this tool previously inserted (by marker), so a
    second run starts from a clean slate. Returns the number removed."""
    removed = 0

    for parent in root.iter():
        for child in list(parent):
            if child.tag in ("Variable", "Function") and child.find("Name") is not None:
                owned=(child.find("Name").text or "").startswith(SHAPE_MARKER)
                if child.tag=='Function':
                    owned=(child.findtext('Name') in {'animRelease','animStageEnter',
                           'animStageStart','animStageFinish','animDone'})
                if owned:
                    parent.remove(child)
                    removed += 1
                    continue
            if child.tag in ("Text", "Rectangle", "Oval", "Group", "Polyline",
                              "ViewArea", "Camera3D", "Light3D", "Control"):
                name_el = child.find("Name")
                if name_el is not None and (name_el.text or "").startswith(SHAPE_MARKER):
                    parent.remove(child)
                    removed += 1
                    continue
            if child.tag == "SimulationExperiment":
                name_el = child.find("Name")
                if name_el is not None and name_el.text == EXPERIMENT_MARKER:
                    parent.remove(child)
                    removed += 1

    return removed


def iter_shapes_by_prefix(root: ET.Element, prefix: str) -> Iterable[ET.Element]:
    for e in root.iter():
        name_el = e.find("Name") if list(e) else None
        if name_el is not None and (name_el.text or "").startswith(prefix):
            yield e
