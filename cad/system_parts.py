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
from parts import hd, hole


# --- machined parts ------------------------------------------------------------------------------------------
def base_plate(depth, y_min, holes):
    """Base plate, top face at z = 0. `holes` are (x, y) positions of M5 holes. Machined or, for a first prototype, plywood."""
    part = Pos(0, y_min + depth / 2, -P.BASE_T / 2) * Box(P.BASE_X, depth, P.BASE_T)
    for x, y in holes:
        part -= hole("z", P.M5_CLEAR, P.BASE_T + 2, x, y, -P.BASE_T / 2)
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



def phantom_block():
    """Phantom container with its block: 60 x 60 x PH_HEIGHT, floor at z = 3."""
    return Pos(0, 0, 3.0 + P.PH_HEIGHT / 2) * Box(P.PHANTOM_BOX, P.PHANTOM_BOX, P.PH_HEIGHT)


PRINTED_V2 = {
    "quick_knob": quick_knob,
}
MACHINED_V2 = {}
