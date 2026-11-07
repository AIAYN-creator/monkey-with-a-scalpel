"""Frame stiffening (card mech-z): two diagonal braces from each upright to the base (the crossbeam is a printed hollow box now, see beam.py).

The brackets that hold the braces are printed (`brace_bracket`) but not drawn in the assembly yet. The profiles are dummies of
the real extrusion; the effective stiffness of the joints is an assumption (see cad/mech_review.py).
"""
import math

import params as P
import system_parts as SP
from build123d import Box, Pos
from layout import aim
from parts import hd, hole

BRACE_TOP = (-5.0, 190.0)  # y, z of the upper end of a brace, on the outer face of the upright
BRACE_BOTTOM = (-125.0, 20.0)  # y, z of the lower end of a brace, on the base plate


def brace_bracket():
    """Angle bracket between a brace and an upright or the base plate (an L of 4 mm plate, two M5 holes per leg)."""
    part = Pos(0, 0, 2.0) * Box(30.0, 30.0, 4.0) + Pos(0, -13.0, 17.0) * Box(30.0, 4.0, 30.0)
    for x in (-8.0, 8.0):
        part -= hole("z", hd(P.M5_CLEAR), 6.0, x, 6.0, 2.0)
        part -= hole("y", hd(P.M5_CLEAR), 6.0, x, -13.0, 20.0)
    return part


PARTS = {
    "brace_bracket": (brace_bracket, "printed"),
}


def fixed(variant, setback):
    out = {}
    # diagonal braces in the plane of each outer face of the uprights, from the upright down and back to the base
    y1, z1 = BRACE_TOP
    y2, z2 = BRACE_BOTTOM
    length = math.hypot(y2 - y1, z2 - z1)
    for sign in (-1, 1):
        x = sign * (P.UPRIGHT_X + P.PROFILE)
        start = (x, y1, z1)
        direction = (0.0, y2 - y1, z2 - z1)
        out[f"brace_{'r' if sign > 0 else 'l'}"] = (Pos(*start) * aim(direction) * SP.profile(length), "purchased")
    return out
