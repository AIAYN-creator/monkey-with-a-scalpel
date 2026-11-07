"""Tool interface (card t-mount): the latch, the presence sensor mount, the holder of the floating connector and the tool rack.

How a tool is held (D-27 and dec-iface): two dowel pins of 3 mm give the position, two M4 with hand knobs hold the tool on the Z carriage
plate (they stay in tool_parts of system.py until the knobs are replaced). This module adds what the contract asks for around that:

- `latch_lever` and `latch_hook`: a cam latch that replaces the two knobs with one lever. Not placed: an alternative to the knobs,
  to try on the printed prototype.
- `presence_tab` and `presence_bracket`: a tab on the tool and a micro switch mount on the carriage plate; the switch is the presence
  sensor the firmware reads (`Inputs::tool_present`). Not placed: the switch and its position are not chosen (measure S4).
- `tool_connector_holder`: holder of the floating 12-circuit connector. Not placed: the connector is not chosen. The position of the
  tool never comes from this connector.
- `tool_rack_segment`: a base with three cradles that stand a tool upright. **Placed** on the base plate outside the reach of the
  gantry (see below).

The gantry cannot change tools by itself: with 100 mm of travel per axis the tool tip only reaches a 100 mm square, and a rack of eight
or nine tools needs about 340 mm. The tools are changed by hand, at rest, with `TOOL OFF`, in a change pose, and the rack holds the tools
that are not mounted. An automatic change needs more travel in one axis (about 200 mm) or a carousel: a decision for the human.

Tolerances to measure before printing (all assumed here): fit of the 3 mm dowels (HOLE_COMP of the printer), repeatability of the
position after a change (target to be set by `p1-09`), force of the latch, wear of the printed holes over 100 changes.
"""
import params as P
from build123d import Box, Cylinder, Pos
from layout import work_y
from parts import hd, hole

RACK_PITCH = 38.0
RACK_X = (RACK_PITCH * 3, 50.0, 6.0)  # length, depth and base thickness of a segment of three positions
CRADLE = (34.0, 40.0, 55.0)  # x, y, z of a cradle block
RACK_CENTRE_X = 172.5 - 0.075 * P.DX  # centre of the right-hand segments; the tools never reach them (the gantry covers x -50 to +50)


def tool_connector_holder():
    """Holder for the floating 12-circuit connector of the tool head (cable end, strain relief by zip tie). Pocket
    22 x 9 mm assumed; NOT placed in the assembly: the connector is not chosen. The tool position comes from the
    two pins, never from this connector.
    """
    plate = Pos(0, 0, 3.0) * Box(40.0, 20.0, 6.0)
    part = plate - Pos(0, 0, 4.5) * Box(22.4, 9.4, 6.0)
    for x in (-16.0, 16.0):
        part -= hole("z", hd(P.M3_CLEAR), 10, x, 0.0, 3.0)
    part -= Pos(0, 7.5, 3.0) * Box(3.6, 2.2, 10.0)
    return part


def latch_hook():
    """Hook on the tool backplate that the lever pulls: a block with a slot for the lever's cam and two M3 holes. Floor at z = 0."""
    part = Pos(0, 0, 8.0) * Box(24.0, 14.0, 16.0)
    part -= Pos(0, 0, 11.0) * Box(14.0, 16.0, 6.0)  # the slot the cam goes through
    for x in (-8.0, 8.0):
        part -= hole("y", hd(P.M3_CLEAR), 16.0, x, 0, 4.0)
    return part


def latch_lever():
    """Cam lever: a 60 mm arm with a 20 mm eccentric disc at one end and a 4 mm pivot hole. Printed flat, thickness 8 mm along z."""
    arm = Pos(30.0, 0, 4.0) * Box(60.0, 10.0, 8.0)
    cam = Pos(0, 0, 4.0) * Cylinder(10.0, 8.0)
    part = arm + cam
    part -= hole("z", hd(4.0), 10.0, 3.0, 0, 4.0)  # the pivot, 3 mm off the centre of the disc so that it pulls as it turns
    return part


def presence_tab():
    """Tab on the tool backplate that closes the presence switch when the tool is seated: 14 x 8 x 3 mm and two M3 holes."""
    part = Pos(0, 0, 1.5) * Box(14.0, 8.0, 3.0) + Pos(0, 5.0, 7.5) * Box(14.0, 2.0, 15.0)
    for x in (-4.0, 4.0):
        part -= hole("z", hd(P.M3_CLEAR), 4.0, x, 0.0, 1.5)
    return part


def presence_bracket():
    """Bracket for the presence micro switch on the Z carriage plate: a foot with two M3 holes and a wall with the two M2 holes of the
    switch (hole spacing SWITCH_HOLE_PITCH). The switch actuates towards +Y."""
    foot = Pos(0, 0, 2.0) * Box(26.0, 16.0, 4.0)
    wall = Pos(0, -6.0, 12.0) * Box(26.0, 4.0, 16.0)
    part = foot + wall
    for x in (-8.0, 8.0):
        part -= hole("z", hd(P.M3_CLEAR), 6.0, x, 3.0, 2.0)
    for x in (-P.SWITCH_HOLE_PITCH / 2, P.SWITCH_HOLE_PITCH / 2):
        part -= hole("y", hd(2.0), 6.0, x, -6.0, 12.0)
    return part


def tool_rack_segment():
    """Base with three cradles that stand a tool upright by its backplate: a U notch in each block. Three positions on a 38 mm pitch;
    it fits the print volume. Fixing to the base plate by two M5 holes in the base. Local frame: floor at z = 0, centred on x and y."""
    part = Pos(0, 0, RACK_X[2] / 2) * Box(RACK_X[0], RACK_X[1], RACK_X[2])
    for k in (-1, 0, 1):
        x = k * RACK_PITCH
        part += Pos(x, 0, RACK_X[2] + CRADLE[2] / 2) * Box(CRADLE[0], CRADLE[1], CRADLE[2])
        part -= Pos(x, 0, RACK_X[2] + CRADLE[2] - 15.0) * Box(24.0, CRADLE[1] + 2, 32.0)  # the U notch for the backplate
    for x in (-RACK_X[0] / 2 + 8.0, RACK_X[0] / 2 - 8.0):
        part -= hole("z", hd(P.M5_CLEAR), RACK_X[2] + 2, x, 0.0, RACK_X[2] / 2)
    return part


PARTS = {
    "tool_connector_holder": (tool_connector_holder, "printed"),
    "latch_hook": (latch_hook, "printed"),
    "latch_lever": (latch_lever, "printed"),
    "presence_tab": (presence_tab, "printed"),
    "presence_bracket": (presence_bracket, "printed"),
    "tool_rack_segment": (tool_rack_segment, "printed"),
}


def fixed(variant, setback):
    """Three rack segments on the base plate, outside the reach of the gantry: right-front, right-back and left-back."""
    wy = work_y(variant, setback)
    out = {}
    out["tool_rack_right_front"] = (Pos(RACK_CENTRE_X, wy + 105.0, 0) * tool_rack_segment(), "printed")
    out["tool_rack_right_back"] = (Pos(RACK_CENTRE_X, wy - 105.0, 0) * tool_rack_segment(), "printed")
    out["tool_rack_left_back"] = (Pos(-RACK_CENTRE_X, wy - 105.0, 0) * tool_rack_segment(), "printed")
    return out


# The tool is meant to touch the rack when it docks: with a large travel the gantry reaches the rack, so the head parts that seat in a
# cradle are allowed to overlap the rack segments (the docking geometry itself is checked by the tool-mount module test).
_HEAD = ("tool_backplate", "hamilton_clamp", "wrist_cradle", "wrist_yoke", "wrist_a_base", "syringe_needle", "syringe_barrel", "syringe_plunger",
        "actuator_body", "actuator_shaft", "wrist_sector_b_front", "wrist_sector_b_rear", "wrist_motor_mount_b")
_RACK = ("tool_rack_right_front", "tool_rack_right_back", "tool_rack_left_back")
ALLOWED = {frozenset((h, r)) for h in _HEAD for r in _RACK}

