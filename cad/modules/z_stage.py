"""Y carriage, riser and Z stage: the L bracket on the Y carriage, the Z plate, rail, screw, motor, knob and top switch,
and the Z carriage with its printed plate."""
import math

import params as P
import parts
import system_parts as SP
from build123d import Box, Cylinder, Pos, Rot
from layout import Z_PLATE_CENTRE, Z_PLATE_LEN, Z_PLATE_PATTERN_X
from parts import hd, hole


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


PARTS = {"z_riser": (z_riser, "machined"), "z_knob": (z_knob, "printed")}
ALLOWED = {
    frozenset(("z_screw", "z_motor")),
    frozenset(("z_screw", "z_knob")),
    frozenset(("z_motor", "z_knob")),
}


def moving(pose):
    xc, yc, zc = pose.xc, pose.yc, pose.zc
    y_car, y_pf, y_leg = pose.y_car, pose.y_pf, pose.y_leg
    y_seat = pose.y_seat
    out = {}
    out["y_carriage"] = (Pos(xc, yc, y_seat) * SP.carriage("y"), "purchased", "y")
    y_top = y_seat + P.CARR_H
    out["z_riser"] = (Pos(xc, yc, y_top) * z_riser(), "machined", "y")
    z_plate = Pos(xc, y_leg, Z_PLATE_CENTRE) * Rot(270, 0, 270) * parts.stage_plate(Z_PLATE_LEN, Z_PLATE_PATTERN_X)
    out["z_plate"] = (z_plate, "machined", "y")
    z_rot = Rot(270, 0, 270)
    out["z_rail"] = (Pos(xc, y_pf, Z_PLATE_CENTRE) * z_rot * SP.rail(180.0 + P.DZ, "x"), "purchased", "y")
    out["z_screw"] = (Pos(xc + 58.0, y_pf + 8.0, 95.0) * SP.screw(240.0 + P.DZ), "dummy", "y")
    out["z_motor"] = (Pos(xc + 58.0, y_pf + 8.0, 295.0 + P.DZ) * SP.motor17(), "dummy", "y")
    out["z_knob"] = (Pos(xc + 58.0, y_pf + 8.0, 335.0 + P.DZ + 8.0) * z_knob(), "printed", "y")
    out["z_carriage"] = (Pos(xc, y_pf, zc) * z_rot * SP.carriage("x"), "purchased", "z")
    out["z_carriage_plate"] = (Pos(xc, y_car, zc) * parts.z_carriage_plate(), "printed", "z")
    out["z_switch_bracket"] = (
        Pos(xc + 25.0, y_pf, 270.0 + P.DZ) * Rot(270, 0, 270) * Rot(0, 0, 180) * SP.limit_switch_bracket(), "printed", "y")
    return out
