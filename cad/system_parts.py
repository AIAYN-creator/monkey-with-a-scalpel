"""Provisional parts of the whole system, version 0.2: frame, riser, camera mounts, limit switches, controls, wrist.

Same conventions as parts.py. Each function builds one part in its own local frame; system.py places them.
The dummies (profiles, rails, motors, cameras...) are envelopes to check space, not parts to make.
"""
import math

import params as P
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    Rot,
    extrude,
)
from parts import hd, hole, interface_cut


# --- machined parts ------------------------------------------------------------------------------------------
def base_plate(depth, y_min, holes):
    """Base plate, top face at z = 0. `holes` are (x, y) positions of M5 holes. Machined or, for a first prototype, plywood."""
    part = Pos(0, y_min + depth / 2, -P.BASE_T / 2) * Box(P.BASE_X, depth, P.BASE_T)
    for x, y in holes:
        part -= hole("z", P.M5_CLEAR, P.BASE_T + 2, x, y, -P.BASE_T / 2)
    return part


def z_riser():
    """L bracket from the Y carriage to the Z plate. Origin: centre of the Y carriage, top face (z = 0). Aluminium 6 mm.

    The foot lies on the carriage; the leg hangs at ARM_REACH so the tool clears the end of the Y plate at full travel.
    """
    reach = P.ARM_REACH
    foot = Pos(5.0, (reach + 3.0 - 25.0) / 2, 3.0) * Box(62, reach + 28.0, 6)
    leg = Pos(5.0, reach, -17.0) * Box(62, 6, 46)  # z from -40 to 6
    part = foot + leg
    for x in (-10.0, 10.0):
        for y in (-10.0, 10.0):
            part -= hole("z", P.M3_CLEAR, 10, x, y, 3.0)  # carriage pattern
    for x in (-10.0, 10.0):
        for z in (-30.0, -10.0):
            part -= hole("y", P.M3_CLEAR, 10, x, reach, z)  # Z plate pattern, tapped M3 in the plate
    return part


def wrist_yoke(setback):
    """Fixed part of the active wrist (A axis, tilt about X). Tool frame: pivot axis through the origin, along X.

    Back plate against the Z carriage plate, two arms to the pivot with a 608 bearing pocket each.
    `setback` is the distance from the pivot axis to the front face of the back plate.
    """
    plate_y0, plate_y1 = -(setback + 6.0), -setback
    plate = Pos(0, (plate_y0 + plate_y1) / 2, 45.5) * Box(70, 6, 125)  # z from -17 to 108
    part = plate
    for sign in (-1, 1):
        arm = Pos(sign * 31.0, (plate_y0 + 8.0) / 2, 0) * Box(8, 8.0 - plate_y0, 34)  # x from 27 to 35
        part += arm
        part -= hole("x", P.BEARING_OD + P.HOLE_COMP, P.BEARING_W, sign * (35.0 - P.BEARING_W / 2), 0, 0)
        part -= hole("x", hd(9.0), 12, sign * 31.0, 0, 0)
    part -= interface_cut(z0=60.0, y0=(plate_y0 + plate_y1) / 2, length=20)
    return part


def wrist_cradle():
    """Moving part of the active wrist: plate behind the tool backplate, two cheeks that carry the pivot bolts."""
    plate = Pos(0, -23.0, 59.0) * Box(52, 6, 102)  # y from -26 to -20, z from 8 to 110
    part = plate
    for sign in (-1, 1):
        part += Pos(sign * 23.0, -9.0, 0) * Box(6, 34, 16)  # y from -26 to 8
        part -= hole("x", hd(8.0), 10, sign * 23.0, 0, 0)
    part -= interface_cut(z0=60.0, y0=-23.0, length=20)
    return part


# --- printed parts -------------------------------------------------------------------------------------------
def camera_wedge(pitch):
    """Camera mount that tilts the camera `pitch` degrees: flat face with two M5 on the slot axis, 1/4-20 on the tilted face."""
    t_thin = 8.0
    t_thick = t_thin + 40.0 * math.tan(math.radians(pitch))
    with BuildPart() as wedge:
        with BuildSketch(Plane.YZ):
            Polygon((0, -20), (t_thin, -20), (t_thick, 20), (0, 20), align=None)
        extrude(amount=20, both=True)
    part = wedge.part
    for z in (-12.0, 12.0):
        part -= hole("y", hd(P.M5_CLEAR), 2 * t_thick, 0, 0, z)
    centre_y = t_thin + 20.0 * math.tan(math.radians(pitch))
    part -= Pos(0, centre_y, 0) * (Rot(-pitch, 0, 0) * hole("y", P.CAM_THREAD + P.HOLE_COMP, 30))
    return part


def limit_switch_bracket():
    """Foot with two M5 holes and a wall that carries a micro switch (two M2 holes). The switch actuates towards +Y."""
    foot = Pos(0, 0, 2.0) * Box(30, 20, 4)
    wall = Pos(0, -8.0, 13.0) * Box(30, 4, 18)
    part = foot + wall
    part -= Pos(0, 8.0, 2.0) * Box(3.6, 2.2, 8.0)  # zip-tie slot for the switch cable strain relief
    for x in (-10.0, 10.0):
        part -= hole("z", hd(P.M5_CLEAR), 10, x, 3.0, 2.0)
    for x in (-P.SWITCH_HOLE_PITCH / 2, P.SWITCH_HOLE_PITCH / 2):
        part -= hole("y", hd(2.0), 10, x, -8.0, 13.0)
    return part


def limit_flag():
    """Tab that trips a limit switch: foot with two M3 holes and a vertical tab."""
    foot = Pos(0, 0, 1.5) * Box(24, 10, 3)
    tab = Pos(0, 3.5, 10.0) * Box(24, 3, 14)
    part = foot + tab
    for x in (-6.0, 6.0):
        part -= hole("z", hd(P.M3_CLEAR), 10, x, -2.0, 1.5)
    return part


def control_panel():
    """Enclosure for the emergency stop (22 mm), the abort button (16 mm) and a status LED, with two mounting flanges.

    Front face towards +Y. Open underneath for the wiring (printed upside down).
    """
    outer = Pos(0, 0, 25.0) * Box(150, 60, 50)
    inner = Pos(0, -1.5, 23.5) * Box(144, 57, 47)
    part = outer - inner
    for sign in (-1, 1):
        part += Pos(sign * 85.0, 0, 2.0) * Box(20, 40, 4)
        part -= hole("z", hd(P.M4_CLEAR), 10, sign * 85.0, 0, 2.0)
    part -= hole("y", P.ESTOP_D + P.HOLE_COMP, 10, -40.0, 29.0, 25.0)
    part -= hole("y", P.ABORT_D + P.HOLE_COMP, 10, 10.0, 29.0, 25.0)
    part -= hole("y", P.LED_D + P.HOLE_COMP, 10, 45.0, 29.0, 25.0)
    for x in (-40.0, 40.0):
        part -= hole("y", 12.5, 10, x, -29.0, 25.0)  # rear cable glands (provisional size)
    return part


def z_knob():
    """Hand wheel for the upper shaft of the dual-shaft Z motor (manual raising of the tool with the power off)."""
    disc = Pos(0, 0, 6.0) * Cylinder(25.0, 12.0)
    part = disc
    for k in range(6):
        a = math.radians(60 * k)
        part -= hole("z", 8.0, 14, 15.0 * math.cos(a), 15.0 * math.sin(a), 6.0)
    part -= hole("z", hd(5.0), 14, 0, 0, 6.0)
    part -= Pos(0, 3.0, 6.0) * Box(5.2 + 0.4, 1.0, 14)  # D flat of the shaft: replace by measurement
    part -= hole("x", hd(2.5), 30, 0, 0, 6.0)  # grub screw, heat-set insert
    return part


def quick_knob():
    """Hand knob for the two M4 of the tool interface (tool-free change; the dowels keep the position). Base at z = 0."""
    part = Pos(0, 0, 4.0) * Cylinder(10.0, 8.0)
    for k in range(8):
        a = math.radians(45 * k)
        part -= hole("z", 4.0, 10, 10.0 * math.cos(a), 10.0 * math.sin(a), 4.0)
    part -= hole("z", hd(P.M4_CLEAR), 12, 0, 0, 4.0)
    part -= hole("z", 8.2, 3.2, 0, 0, 1.6)  # M4 nut pocket
    return part


# --- dummies (envelopes, not parts to make) ------------------------------------------------------------------
def profile(length, axis="z"):
    """2020 profile from the origin along `axis`, without its T-slots (envelope)."""
    part = Pos(0, 0, length / 2) * Box(P.PROFILE, P.PROFILE, length)
    part -= Pos(0, 0, length / 2) * Cylinder(2.1, length)
    if axis == "x":
        part = Rot(0, 90, 0) * part
    elif axis == "y":
        part = Rot(-90, 0, 0) * part
    return part


def rail(length, axis):
    """Size-12 rail envelope centred on the origin, seat at z = 0."""
    box = Pos(0, 0, P.RAIL_H / 2) * Box(length, P.RAIL_W, P.RAIL_H)
    return box if axis == "x" else Rot(0, 0, 90) * box


def carriage(axis):
    """Size-12 carriage envelope centred on the origin, seat at z = 0, with the rail channel cut out."""
    box = Pos(0, 0, P.CARR_H / 2) * Box(P.CARR_L, P.CARR_W, P.CARR_H)
    box -= Pos(0, 0, P.RAIL_H / 2) * Box(P.CARR_L + 2, P.RAIL_W, P.RAIL_H)
    return box if axis == "x" else Rot(0, 0, 90) * box


def motor17(length=40.0):
    """NEMA 17 envelope: face on the XY plane at z = 0, body towards +Z."""
    return Pos(0, 0, length / 2) * Box(P.N17_FACE, P.N17_FACE, length)


def screw(length, d=8.0):
    """T8 screw envelope along Z from the origin."""
    return Pos(0, 0, length / 2) * Cylinder(d / 2, length)


def switch_dummy():
    """Micro switch envelope seated on the bracket wall (centre at the origin, actuating towards +Y)."""
    return Box(P.SWITCH_L, P.SWITCH_W, P.SWITCH_H)


def camera_body():
    """Camera envelope: lens towards +Z, centre at the origin."""
    w, h, d = P.CAM_BODY
    return Box(w, h, d)


def electronics_box():
    """Envelope of the power supply, drivers and ESP32 board."""
    return Pos(0, 0, 30.0) * Box(200, 95, 60)


def cable_clip_2020():
    """Clip for the 6 mm slot of a 2020 profile with an open saddle for a cable bundle (about 12 mm).

    Local frame: z = 0 at the profile face, +z away from it; the stem and the T head go into the slot (-z).
    The slot dimensions are typical values to check on the real profile.
    """
    stem = Pos(0, 0, -3.0) * Box(5.6, 10.0, 6.0)
    head = Pos(0, 0, -7.0) * Box(10.2, 10.0, 2.0)
    saddle = Pos(0, 0, 8.0) * Box(20.0, 10.0, 16.0)
    part = stem + head + saddle
    part -= Pos(0, 0, 8.5) * Rot(90, 0, 0) * Cylinder(6.0, 12.0)
    part -= Pos(0, 0, 14.0) * Box(11.0, 12.0, 10.0)  # open top of the saddle
    return part


ENC_X, ENC_Y, ENC_Z, ENC_WALL = 210.0, 105.0, 85.0, 3.0


def electronics_enclosure():
    """Printed tray for the supply, contactor, drivers and ESP32, open on top (the lid screws into four posts).

    Local frame: centred on x and y, floor at z = 0. The rear wall (-y) carries eleven 12.2 mm holes for panel
    connectors or cable glands, one per cable of the wiring map (provisional size). Fixing to the base is not
    designed: four 4.4 mm holes in the floor, reachable with the lid off.
    """
    outer = Pos(0, 0, ENC_Z / 2) * Box(ENC_X, ENC_Y, ENC_Z)
    inner = Pos(0, 0, ENC_WALL + (ENC_Z - ENC_WALL) / 2 + 0.01) * Box(
        ENC_X - 2 * ENC_WALL, ENC_Y - 2 * ENC_WALL, ENC_Z - ENC_WALL)
    part = outer - inner
    px, py = ENC_X / 2 - ENC_WALL - 5.0, ENC_Y / 2 - ENC_WALL - 5.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            part += Pos(sx * px, sy * py, ENC_WALL + (ENC_Z - ENC_WALL) / 2) * Cylinder(4.0, ENC_Z - ENC_WALL)
            part -= hole("z", 2.5, 12.0, sx * px, sy * py, ENC_Z - 6.0)
    for i in range(11):
        part -= hole("y", 12.2 + P.HOLE_COMP, 10, -85.0 + 17.0 * i, -ENC_Y / 2 + ENC_WALL / 2, 45.0)
    for x in (-60.0, 60.0):
        for y in (-25.0, 25.0):
            part -= hole("z", hd(P.M4_CLEAR), 10, x, y, ENC_WALL / 2)
    return part


def enclosure_lid():
    """Lid of the electronics tray with vent slots and four M3 holes. Local frame: z = 0 at the underside."""
    part = Pos(0, 0, 1.5) * Box(ENC_X, ENC_Y, 3.0)
    px, py = ENC_X / 2 - ENC_WALL - 5.0, ENC_Y / 2 - ENC_WALL - 5.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            part -= hole("z", hd(P.M3_CLEAR), 10, sx * px, sy * py, 1.5)
    for i in range(8):
        part -= Pos(-70.0 + 20.0 * i, 0, 1.5) * Box(4.0, 40.0, 10.0)
    return part


def chain_mount():
    """End bracket for a drag chain (the same part serves the fixed and the moving ends): a foot with two M4 holes
    and a lug for the chain end link with two M3 holes. Chain inner width 20 mm assumed. NOT placed in the
    assembly: the chain route and size are not decided.
    """
    foot = Pos(0, 0, 3.0) * Box(40.0, 30.0, 6.0)
    lug = Pos(0, -10.0, 17.0) * Box(30.0, 8.0, 22.0)
    part = foot + lug
    for x in (-14.0, 14.0):
        part -= hole("z", hd(P.M4_CLEAR), 10, x, 8.0, 3.0)
    for z in (11.0, 23.0):
        part -= hole("y", hd(P.M3_CLEAR), 20, 0.0, -10.0, z)
    return part


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


def phantom_block():
    """Phantom container with its block: 60 x 60 x PH_HEIGHT, floor at z = 3."""
    return Pos(0, 0, 3.0 + P.PH_HEIGHT / 2) * Box(P.PHANTOM_BOX, P.PHANTOM_BOX, P.PH_HEIGHT)


PRINTED_V2 = {
    "camera_wedge_45": lambda: camera_wedge(45),
    "limit_switch_bracket": limit_switch_bracket,
    "limit_flag": limit_flag,
    "control_panel": control_panel,
    "z_knob": z_knob,
    "quick_knob": quick_knob,
    "wrist_cradle": wrist_cradle,
    "wrist_yoke": lambda: wrist_yoke(110.0),
    "cable_clip_2020": cable_clip_2020,
    "electronics_enclosure": electronics_enclosure,
    "enclosure_lid": enclosure_lid,
    "chain_mount": chain_mount,
    "tool_connector_holder": tool_connector_holder,
}
MACHINED_V2 = {
    "z_riser": z_riser,
    "base_plate": lambda: base_plate(480.0, -130.0, [(-40.0, -40.0)]),
}
