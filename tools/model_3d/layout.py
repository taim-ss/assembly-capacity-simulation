"""Floor-plan geometry and colour palette for the 3D layer.

Units are model-space "pixels" (AnyLogic's X/Y, 1 unit ~= 1 cm by PLE
convention at default scale). Station order matches the brief:
Source/Dock -> Kitting -> Assembly -> Test -> Quality -> Handover ->
Sink/Shipping, laid out left to right along Y=0, with a rework return path
drawn as a second lane below the main row from Test back to Assembly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MAX_UNITS_PER_STAGE = 6
STATION_SPACING_X = 220
STATION_Y = 300
STATION_W = 140
STATION_H = 100
STATION_DEPTH_Z = 80  # extrusion height (ZHeight) for the "building" box

LANE_OFFSET_Y = 90        # queue lane sits this far above the station box
LANE_SLOT_SPACING = 22
LANE_VISIBLE_SLOTS = 8     # slots actually drawn; beyond this show "+N" text

SERVICE_SLOT_SPACING_X = 20
SERVICE_SLOT_Y_OFFSET = 10

REWORK_LANE_Y = STATION_Y + STATION_H + 70

GROUND_MARGIN = 160


@dataclass(frozen=True)
class Station:
    key: str              # short id used in variable/shape names
    label: str             # display label
    stage_index: Optional[int]  # 0..4 index into busy[]/queued[]/STAGES, or None for dock/sink
    pool_var: Optional[str]      # ResourcePool block name in Main, or None
    service_var: Optional[str]   # Service/Source/Sink block name in Main, used for queueSize()/size()
    x: int
    color: str


# x positions: 7 stations, evenly spaced
_N = 7
STATIONS: list[Station] = [
    Station("dock", "INCOMING WORK ORDERS", None, None, "source",
             GROUND_MARGIN + 0 * STATION_SPACING_X, "#8d99ae"),
    Station("kitting", "1  PREPARE PARTS", 0, "kittingPool", "kittingService",
             GROUND_MARGIN + 1 * STATION_SPACING_X, "#4895ef"),
    Station("assembly", "2  ASSEMBLE SENSOR", 1, "assemblyPool", "assemblyService",
             GROUND_MARGIN + 2 * STATION_SPACING_X, "#4361ee"),
    Station("test", "3  FUNCTIONAL TEST", 2, "testPool", "testService",
             GROUND_MARGIN + 3 * STATION_SPACING_X, "#f3722c"),
    Station("quality", "4  QUALITY CHECK", 3, "qualityPool", "qualityService",
             GROUND_MARGIN + 4 * STATION_SPACING_X, "#f9c74f"),
    Station("handover", "5  PACK & LABEL", 4, "handoverPool", "handoverService",
             GROUND_MARGIN + 5 * STATION_SPACING_X, "#90be6d"),
    Station("ship", "READY TO SHIP", None, None, "sink",
             GROUND_MARGIN + 6 * STATION_SPACING_X, "#2b2d42"),
]

STATION_BY_KEY = {s.key: s for s in STATIONS}
# stage_index (0..4) -> Station, for the 5 capacity stages only
STAGE_STATIONS = {s.stage_index: s for s in STATIONS if s.stage_index is not None}

GROUND_WIDTH = STATIONS[-1].x - STATIONS[0].x + 2 * GROUND_MARGIN
GROUND_HEIGHT = 480
GROUND_X = STATIONS[0].x - GROUND_MARGIN
GROUND_Y = STATION_Y - 180

ASSEMBLY_X = STATION_BY_KEY["assembly"].x
TEST_X = STATION_BY_KEY["test"].x

# Job box colours (hex, converted to Java Color in hooks.py)
COLOR_DEFAULT = "#adb5bd"
COLOR_IN_SERVICE = "#43aa8b"
COLOR_WAITING = "#577590"
COLOR_REWORK = "#e63946"
COLOR_DONE = "#2b9348"

KPI_PANEL_X = GROUND_X + 10
KPI_PANEL_Y = GROUND_Y - 150

TITLE_X = GROUND_X + 10
TITLE_Y = GROUND_Y - 190
