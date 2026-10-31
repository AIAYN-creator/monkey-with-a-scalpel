"""Provisional parametric CAD of the printed and machined parts, version 0.1.

Coordinates of the tool head: the syringe axis is Z, the needle hub plane is z = 0 and the needle points to -Z.
Run `python cad/build.py` to build every part, check it and export the STL files.
"""
import math

import params as P
from build123d import (
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    Rot,
    extrude,
    fillet,
)


def hd(nominal):
    """Printed hole diameter: nominal plus the print compensation."""
    return nominal + P.HOLE_COMP


def hole(axis, d, length, x=0.0, y=0.0, z=0.0):
    """A cylinder used to cut a hole, along `axis`, centred on (x, y, z)."""
    cylinder = Cylinder(d / 2, length)
    if axis == "x":
        cylinder = Rot(0, 90, 0) * cylinder
    elif axis == "y":
        cylinder = Rot(90, 0, 0) * cylinder
    return Pos(x, y, z) * cylinder


def interface_cut(z0, x0=0.0, y0=0.0, length=40.0):
    """The tool interface pattern, along Y: two dowels and two M4 on a square, centred on (x0, z0)."""
    half = P.IF_PITCH / 2
    cut = hole("y", hd(P.DOWEL_D), length, x0 - half, y0, z0 + half)
    cut += hole("y", hd(P.DOWEL_D), length, x0 + half, y0, z0 - half)
    cut += hole("y", hd(P.M4_CLEAR), length, x0 + half, y0, z0 + half)
    cut += hole("y", hd(P.M4_CLEAR), length, x0 - half, y0, z0 - half)
    return cut


# --- printed parts -------------------------------------------------------------------------------------------
def hamilton_clamp(barrel_od=P.BARREL_OD):
    """Split clamp around the syringe barrel, with a rear plate that bolts to the tool backplate."""
    body_x, body_y, body_z = 22.0, 18.0, 20.0
    plate_x, plate_y, plate_z = 40.0, 5.0, 26.0
    body = fillet(Box(body_x, body_y, body_z).edges().filter_by(Axis.Z), 2.0)
    plate_cy = -(body_y / 2 + plate_y / 2)
    part = body + Pos(0, plate_cy, -3) * Box(plate_x, plate_y, plate_z)
    part -= hole("z", hd(barrel_od) + 0.1, 80)
    slit_y = body_y / 2 - 2.5
    part -= Pos(0, slit_y, 0) * Box(1.0, 10, 40)
    part -= hole("x", hd(P.M3_CLEAR), 60, 0, slit_y, 0)
    for x in (-15.0, 15.0):
        for z in (-9.0, 3.0):
            part -= hole("y", hd(P.M3_CLEAR), 20, x, plate_cy, z)
    return part


def tool_backplate():
    """Vertical plate that carries the clamp (low), the plunger motor mount (high) and the wedge (rear)."""
    z_lo, z_hi = -6.0, 150.0
    part = Pos(0, -17.0, (z_lo + z_hi) / 2) * Box(40, 6, z_hi - z_lo)
    for x in (-15.0, 15.0):  # clamp pattern: clamp centre at z = CLAMP_Z, holes at -9 and +3 from it
        for z in (P.CLAMP_Z - 9.0, P.CLAMP_Z + 3.0):
            part -= hole("y", hd(P.M3_CLEAR), 20, x, -17.0, z)
        part -= hole("y", hd(P.M3_CLEAR), 20, x, -17.0, 136.0)  # plunger motor mount
    part -= interface_cut(z0=60.0, y0=-17.0, length=20)
    return part


def plunger_motor_mount():
    """Shelf that holds the NEMA 11 captive actuator above the syringe, shaft pointing down."""
    cx = P.ACT_OFFSET
    flange = Pos(0, -11.0, 136.0) * Box(40, 6, 28)  # against the front face of the backplate (y = -14)
    shelf = Pos(6.0, 1.0, 147.0) * Box(52, 30, 6)
    part = flange + shelf
    part -= hole("z", hd(P.N11_PILOT), 20, cx, 0, 147.0)
    half = P.N11_HOLES / 2
    for dx in (-half, half):
        for dy in (-half, half):
            part -= hole("z", hd(P.M25_CLEAR), 20, cx + dx, dy, 147.0)
    for x in (-15.0, 15.0):
        part -= hole("y", hd(P.M3_CLEAR), 20, x, -11.0, 136.0)
    return part


def plunger_coupler():
    """Clamps the actuator shaft and captures the plunger button in a side-entry slot. Button centre at the origin."""
    cx = P.ACT_OFFSET
    height = P.BUTTON_T + 0.6  # pocket height
    width = P.BUTTON_D + P.HOLE_COMP
    low, high = 2.5, 5.0  # lower wall (thin: it must clear the barrel top) and upper wall, which pushes the button
    total = low + height + high
    centre_z = -height / 2 - low + total / 2
    part = Pos(6.5, 0, centre_z) * Box(31, 16, total)
    part -= Pos(-4.5, 0, 0) * Box(9, width, height)
    part -= hole("z", width, height, 0, 0, 0)
    wire_z = -height / 2 - low / 2
    part -= Pos(-4.5, 0, wire_z) * Box(9, P.WIRE_SLOT, low)
    part -= hole("z", P.WIRE_SLOT, low, 0, 0, wire_z)
    part -= hole("z", hd(P.ACT_SHAFT_D), 30, cx, 0, 0)
    part -= hole("y", hd(2.5), 30, cx, 0, 3.0)  # set screw, tapped or with a heat-set insert
    return part


def angle_wedge(angle_deg):
    """Fixed-angle wedge between the carriage plate and the tool backplate. Tilt about X, interface on both faces."""
    t_thin = 8.0
    t_thick = t_thin + P.IF_SIZE * math.tan(math.radians(angle_deg))
    with BuildPart() as wedge:
        with BuildSketch(Plane.YZ):
            Polygon((0, -20), (t_thin, -20), (t_thick, 20), (0, 20), align=None)
        extrude(amount=20, both=True)
    part = wedge.part
    part -= interface_cut(z0=0.0, y0=0.0, length=2 * (t_thin + 5))  # flat face, along Y
    centre_y = (t_thin + t_thick) / 2  # the tilted face is normal to Y rotated by -angle about X
    part -= Pos(0, centre_y, 0) * (Rot(-angle_deg, 0, 0) * interface_cut(z0=0.0, y0=0.0, length=2 * (t_thin + 5)))
    return part


def z_carriage_plate():
    """Printed plate on the Z carriage: carriage pattern behind, tool interface in front. Thickness along Y, 0 to 6."""
    part = Pos(10.0, 3.0, -20.0) * Box(70, 6, 70)
    for x in (-P.CARR_B / 2, P.CARR_B / 2):
        for z in (-P.CARR_C / 2, P.CARR_C / 2):
            part -= hole("y", hd(P.M3_CLEAR), 20, x, 3.0, z)
    part -= interface_cut(z0=-33.0, y0=3.0, length=20)
    return part


def nut_bracket():
    """L-bracket that carries the flanged T8 nut of one axis: flange pattern on the upright, two holes in the foot."""
    upright = Pos(0, 3.0, 18.0) * Box(36, 6, 36)
    foot = Pos(0, 12.0, 3.0) * Box(36, 24, 6)
    part = upright + foot
    part -= hole("y", hd(P.NUT_BORE), 20, 0, 3.0, 18.0)
    r = P.NUT_BC / 2
    for dx, dz in ((r, 0), (-r, 0), (0, r), (0, -r)):
        part -= hole("y", hd(P.M3_CLEAR), 20, dx, 3.0, 18.0 + dz)
    for x in (-12.0, 12.0):
        part -= hole("z", hd(P.M3_CLEAR), 20, x, 14.0, 3.0)
    return part


def motor_mount_nema17():
    """Bracket for a NEMA 17 at the end of an axis: motor face upright, two-hole foot."""
    face = Pos(0, 3.0, 23.0) * Box(46, 6, 46)
    foot = Pos(0, 15.0, 3.0) * Box(46, 30, 6)
    part = face + foot
    part -= hole("y", hd(P.N17_PILOT), 20, 0, 3.0, 23.0)
    half = P.N17_HOLES / 2
    for dx in (-half, half):
        for dz in (-half, half):
            part -= hole("y", hd(P.M3_CLEAR), 20, dx, 3.0, 23.0 + dz)
    for x in (-15.0, 15.0):
        part -= hole("z", hd(P.M3_CLEAR), 20, x, 20.0, 3.0)
    return part


def bearing_support_608():
    """Block with a 608 bearing pocket that holds the free end of a T8 screw."""
    part = Pos(0, 8.0, 15.0) * Box(30, 16, 30) + Pos(0, 22.0, 3.0) * Box(30, 12, 6)
    part -= hole("y", P.BEARING_OD + P.HOLE_COMP, P.BEARING_W, 0, P.BEARING_W / 2, 18.0)
    part -= hole("y", hd(9.0), 40, 0, 8.0, 18.0)
    for x in (-10.0, 10.0):
        part -= hole("z", hd(P.M3_CLEAR), 20, x, 22.0, 3.0)
    return part


def camera_plate():
    """Plate for a camera with a 1/4-20 thread, bolted to the T-slot of a 2020 profile with two M5 (v0.2: on the slot axis)."""
    part = Pos(0, 2.5, 0) * Box(60, 5, 40)
    part -= hole("y", P.CAM_THREAD + P.HOLE_COMP, 20, 0, 2.5, 0)
    for z in (-14.0, 14.0):
        part -= hole("y", hd(P.M5_CLEAR), 20, 0, 2.5, z)
    return part


def phantom_tray():
    """Base for the phantom container, with a recess and four M5 mounting holes."""
    part = Pos(0, 0, 4.0) * Box(100, 100, 8)
    part -= Pos(0, 0, 8.0 - 2.5) * Box(P.PHANTOM_BOX + 1.0, P.PHANTOM_BOX + 1.0, 5.0)
    for x in (-40.0, 40.0):
        for y in (-40.0, 40.0):
            part -= hole("z", hd(P.M5_CLEAR), 20, x, y, 4.0)
    return part


def tolerance_coupon():
    """Test piece to measure the printer: holes, slots, a barrel bore, a bearing pocket and thin walls."""
    part = Pos(0, 0, 2.0) * Box(76, 50, 4)
    for i in range(9):
        part -= hole("z", 2.8 + 0.2 * i, 10, -32 + 8 * i, 15.0, 2.0)
    for i in range(5):
        part -= Pos(-28 + 14 * i, 0, 2.0) * Box(2.0 + 0.5 * i, 8, 10)
    part -= hole("z", P.BARREL_OD + 0.2, 10, -22.0, -12.0, 2.0)
    part -= hole("z", P.BARREL_OD + 0.4, 10, -8.0, -12.0, 2.0)
    part -= hole("z", P.BEARING_OD + 0.4, 10, 14.0, -12.0, 2.0)
    for i, w in enumerate((0.8, 1.2, 1.6, 2.0)):
        part += Pos(-21.0 + 14 * i, -21.0, 7.0) * Box(w, 8, 6)
    return part


# --- machined parts (drilling plan; aluminium 6 mm, not printed) ----------------------------------------------
def stage_plate(length=200.0, pattern_x=0.0):
    """Base plate of a stacked axis: rail holes along its axis, the carriage pattern of the previous axis at `pattern_x`.

    The Z plate hangs from its riser, so its pattern sits near the top end (pattern_x = 75).
    """
    part = Pos(0, 5.0, 3.0) * Box(length, 62, 6)
    n = int(length // P.RAIL_PITCH)
    start = -P.RAIL_PITCH * (n - 1) / 2
    for i in range(n):
        part -= hole("z", 2.5, 10, start + P.RAIL_PITCH * i, 0.0, 3.0)  # tapped M3
    for x in (-P.CARR_B / 2, P.CARR_B / 2):
        for y in (-P.CARR_C / 2, P.CARR_C / 2):
            part -= hole("z", P.M3_CLEAR, 10, pattern_x + x, y, 3.0)
    for x in (-12.0, 12.0):
        part -= hole("z", 2.5, 10, x, 28.0, 3.0)  # nut bracket of the previous axis, tapped
    return part


# --- dummies for the assembly (not parts to make) ------------------------------------------------------------
def dummy_syringe(plunger_out=None):
    """Syringe at the origin: barrel from the hub plane up, plunger and button, hub and needle below.

    `plunger_out` is how far the button stands above the barrel top (default: plunger fully out).
    """
    if plunger_out is None:
        plunger_out = P.PLUNGER_OUT + P.STROKE
    barrel = Pos(0, 0, P.BARREL_LENGTH / 2) * Cylinder(P.BARREL_OD / 2, P.BARREL_LENGTH)
    top = P.BARREL_LENGTH + plunger_out
    wire = Pos(0, 0, P.BARREL_LENGTH + (top - P.BARREL_LENGTH) / 2) * Cylinder(0.3, top - P.BARREL_LENGTH)
    button = Pos(0, 0, top + P.BUTTON_T / 2) * Cylinder(P.BUTTON_D / 2, P.BUTTON_T)
    needle = Pos(0, 0, -(P.HUB_LENGTH + P.NEEDLE_LENGTH) / 2) * Cylinder(0.5, P.HUB_LENGTH + P.NEEDLE_LENGTH)
    return barrel, wire + button, needle


def dummy_actuator():
    """NEMA 11 captive actuator on the shelf, shaft down."""
    body = Pos(P.ACT_OFFSET, 0, 150.0 + P.N11_LENGTH / 2) * Box(P.N11_FACE, P.N11_FACE, P.N11_LENGTH)
    shaft_len = 80.0
    shaft = Pos(P.ACT_OFFSET, 0, 150.0 - shaft_len / 2 + 6) * Cylinder(P.ACT_SHAFT_D / 2, shaft_len)
    return body, shaft


def button_top():
    """Height of the button centre with the plunger fully out (the coupler's highest position)."""
    return P.BARREL_LENGTH + P.PLUNGER_OUT + P.STROKE + P.BUTTON_T / 2


PRINTED = {
    "hamilton_clamp": hamilton_clamp,
    "tool_backplate": tool_backplate,
    "plunger_motor_mount": plunger_motor_mount,
    "plunger_coupler": plunger_coupler,
    "angle_wedge_15": lambda: angle_wedge(15),
    "angle_wedge_30": lambda: angle_wedge(30),
    "angle_wedge_45": lambda: angle_wedge(45),
    "z_carriage_plate": z_carriage_plate,
    "nut_bracket": nut_bracket,
    "motor_mount_nema17": motor_mount_nema17,
    "bearing_support_608": bearing_support_608,
    "camera_plate": camera_plate,
    "phantom_tray": phantom_tray,
    "tolerance_coupon": tolerance_coupon,
}
MACHINED = {"stage_plate": stage_plate}
