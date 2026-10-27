"""Builders for individual AnyLogic presentation shapes (Rectangle, Oval,
Text, Polyline, ViewArea, Camera3D), using the property names recovered from
the installed AnyLogic 8.9.10 PLE jars (see model_3d/__init__.py docstring).
All take plain hex colours and convert them to the AnyLogic signed-int ARGB
form AnyLogic stores (the same encoding already used for
SceneBackgroundColor/LineColor in the generated file, e.g. -4144960).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from . import schema


def hex_to_al_color(hex_color: str, alpha: int = 255) -> int:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    argb = (alpha << 24) | (r << 16) | (g << 8) | b
    # Java/AnyLogic stores colors as signed 32-bit ints
    if argb >= 0x80000000:
        argb -= 0x100000000
    return argb


def rectangle3d(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    fill_hex: str,
    z: int = 0,
    z_height: int = 0,
    line_hex: str = "#000000",
    fill_code: Optional[str] = None,
    visible_code: Optional[str] = None,
    draw_3d: bool = True,
    mode: str | None = None,
) -> ET.Element:
    e = ET.Element("Rectangle")
    schema.header(e, name, x, y)
    schema.tag(e, "Width", width)
    schema.tag(e, "Height", height)
    schema.tag(e, "LineStyle", "SOLID")
    schema.tag(e, "LineWidth", 1)
    schema.tag(e, "LineColor", hex_to_al_color(line_hex))
    if fill_code:
        schema.shape_expression(e, "FillColorCode", fill_code)
    else:
        schema.tag(e, "FillColor", hex_to_al_color(fill_hex))
    schema.tag(e, "Rotation", 0)
    schema.tag(e, "Z", z)
    schema.tag(e, "ZHeight", z_height)
    schema.tag(e, "DrawMode", _draw_mode(mode,draw_3d))
    if visible_code:
        schema.shape_expression(e, "VisibleCode", visible_code)
    return e


def oval3d(
    name: str,
    x: int,
    y: int,
    radius_x: int,
    radius_y: int,
    fill_hex: str,
    z: int = 0,
    z_height: int = 0,
    fill_code: Optional[str] = None,
    visible_code: Optional[str] = None,
    draw_3d: bool = True,
    mode: str | None = None,
) -> ET.Element:
    e = ET.Element("Oval")
    schema.header(e, name, x, y)
    schema.tag(e, "RadiusX", radius_x)
    schema.tag(e, "RadiusY", radius_y)
    schema.tag(e, "Circle", "false")
    schema.tag(e, "LineStyle", "SOLID")
    schema.tag(e, "LineWidth", 1)
    schema.tag(e, "LineColor", hex_to_al_color("#000000"))
    if fill_code:
        schema.shape_expression(e, "FillColorCode", fill_code)
    else:
        schema.tag(e, "FillColor", hex_to_al_color(fill_hex))
    schema.tag(e, "Rotation", 0)
    schema.tag(e, "Z", z)
    schema.tag(e, "ZHeight", z_height)
    schema.tag(e, "DrawMode", _draw_mode(mode,draw_3d))
    if visible_code:
        schema.shape_expression(e, "VisibleCode", visible_code)
    return e


def text_shape(
    name: str,
    x: int,
    y: int,
    text: str,
    color_hex: str = "#000000",
    size: int = 12,
    bold: bool = False,
    text_code: Optional[str] = None,
    visible_code: Optional[str] = None,
    mode: str = '2d',
    z: int = 0,
) -> ET.Element:
    e = ET.Element("Text")
    schema.header(e, name, x, y)
    schema.tag(e, "DrawMode", _draw_mode(mode,False))
    schema.tag(e,'Z',z)
    schema.tag(e, "Text", text)
    if text_code:
        schema.shape_expression(e, "TextCode", text_code)
    schema.tag(e, "Color", hex_to_al_color(color_hex))
    font = schema.tag(e, "Font")
    schema.tag(font, "Name", "SansSerif")
    schema.tag(font, "Size", size)
    schema.tag(font, "Style", 1 if bold else 0)
    schema.tag(e, "Alignment", "LEFT")
    if visible_code:
        schema.shape_expression(e, "VisibleCode", visible_code)
    return e


def polyline(name: str, points: list[tuple[int, int]], color_hex: str, width: int = 2,
             dashed: bool = True, mode: str = '2d', z: int = 0) -> ET.Element:
    e = ET.Element("Polyline")
    schema.header(e, name, points[0][0], points[0][1])
    schema.tag(e,'DrawMode',_draw_mode(mode,False));schema.tag(e,'Z',z)
    schema.tag(e, "LineStyle", "DASHED" if dashed else "SOLID")
    schema.tag(e, "LineWidth", width)
    schema.tag(e, "LineColor", hex_to_al_color(color_hex))
    pts = schema.tag(e, "Points")
    for px, py in points:
        p = schema.tag(pts, "Point")
        schema.tag(p, "X", px - points[0][0])
        schema.tag(p, "Y", py - points[0][1])
    schema.tag(e, "LineArrow", "END")
    return e


def _draw_mode(mode: str | None,draw_3d: bool) -> str:
    if mode is None:return 'SHAPE_DRAW_2D3D' if draw_3d else 'SHAPE_DRAW_2D'
    if mode not in ('2d','3d','both'):raise ValueError(f'Unknown shape mode: {mode}')
    return {'2d':'SHAPE_DRAW_2D','3d':'SHAPE_DRAW_3D','both':'SHAPE_DRAW_2D3D'}[mode]


def view_area_3d(name: str, x: int, y: int, width: int, height: int,
                  title: str) -> ET.Element:
    e = ET.Element("ViewArea")
    schema.header(e, name, x, y)
    schema.tag(e, "Width", width)
    schema.tag(e, "Height", height)
    schema.tag(e, "Title", title)
    return e


def camera_3d(name: str, x: int, y: int, z: int, rotation_x: int, rotation_z: int) -> ET.Element:
    e = ET.Element("Camera3D")
    schema.header(e, name, x, y)
    schema.tag(e, "Z", z)
    schema.tag(e, "RotationX", rotation_x)
    schema.tag(e, "RotationZ", rotation_z)
    return e
