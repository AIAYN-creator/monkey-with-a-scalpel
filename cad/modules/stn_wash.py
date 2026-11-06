"""Wash station (card stn-wash): a printed tray with a bath well, a wiper slot and an air-dry nozzle post, standing on the base plate.

The sequence that uses it (flush a fluid tool, dip and wipe the others, dry, retract) is simulated in host/toolsim/wash.py. The
station stands left in front, outside the reach of the gantry (as the tool rack does): with 100 mm of travel the tip only reaches the
square over the phantom, so **a wash by the gantry needs more travel** (card mech-recorrido) or the tool is washed by hand over the
tray. The wells are assumed sizes; the wiper, the pump, the air line and the bath liquid are not drawn.
"""
import params as P
from build123d import Box, Cylinder, Pos
from layout import work_y
from parts import hd, hole

TRAY = (90.0, 70.0, 40.0)  # x, y, z of the tray


def wash_tray():
    """Block with a 40 x 40 x 30 mm bath well, a 3 mm wiper slot beside it and a post for the air nozzle. Local frame: floor at z = 0,
    centred on x and y. Two M5 holes fix it to the base plate."""
    part = Pos(0, 0, TRAY[2] / 2) * Box(*TRAY)
    part -= Pos(-14.0, 0, TRAY[2] - 14.0) * Box(40.0, 40.0, 30.0)  # the bath well, 10 mm floor
    part -= Pos(22.0, 0, TRAY[2] - 6.0) * Box(3.0, 40.0, 14.0)  # the wiper slot
    part += Pos(34.0, 24.0, TRAY[2] + 22.0) * Cylinder(5.0, 44.0)  # post for the air nozzle
    for x in (-38.0, 38.0):
        part -= hole("z", hd(P.M5_CLEAR), TRAY[2] + 2, x, -28.0, TRAY[2] / 2)
    return part


PARTS = {"wash_tray": (wash_tray, "printed")}


def fixed(variant, setback):
    wy = work_y(variant, setback)
    return {"wash_tray_placed": (Pos(60.0, wy + 120.0, 0) * wash_tray(), "printed")}
