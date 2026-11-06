"""USB microscope as an extra view of the tip: the body (envelope), a post and a printed clamp, on the left of the work area.

The microscope looks along +X at the centre of the phantom. It is fixed, so it only sees a small field (MICRO_FOV) around
the target, not the whole travel. The working distance has to be long (MICRO_WD): a typical USB microscope with a few
centimetres of working distance would hit the tool at the end of the X travel. All dimensions are assumed.
"""
import params as P
import system_parts as SP
from build123d import Box, Cylinder, Pos, Rot
from layout import aim, work_y
from parts import hd, hole

CLAMP = (36.0, 46.0, 46.0)  # x, y, z of the clamp block


def microscope_body():
    """Envelope of the microscope: axis along +Z, lens at the +Z end, centred on the origin."""
    return Cylinder(P.MICRO_D / 2, P.MICRO_L)


def microscope_clamp():
    """Split clamp that holds the body: block with a bore along X, a slit on top and two M4 clamp screws.

    Local frame: centred on the origin, bore along X. The post goes under it.
    """
    part = Box(*CLAMP)
    part -= Rot(0, 90, 0) * Cylinder((P.MICRO_D + 0.4) / 2, CLAMP[0] + 2)
    part -= Pos(0, 0, CLAMP[2] / 2 - 4.0) * Box(CLAMP[0] + 2, 1.6, 10.0)  # slit
    for y in (-17.0, 17.0):
        part -= hole("z", hd(P.M4_CLEAR), CLAMP[2] + 2, 0, y, 0)
    return part


PARTS = {"microscope_clamp": (microscope_clamp, "printed")}


def fixed(variant, setback):
    wy = work_y(variant, setback)
    xm = -P.MICRO_WD - 30.0  # clamp position: the lens is MICRO_WD from the target, the clamp 30 mm behind the lens
    z = P.MICRO_Z
    out = {}
    out["microscope_post"] = (Pos(xm, wy, 0) * SP.profile(z - CLAMP[2] / 2), "purchased")
    out["microscope_clamp"] = (Pos(xm, wy, z) * microscope_clamp(), "printed")
    centre = -P.MICRO_WD - P.MICRO_L / 2
    out["microscope"] = (Pos(centre, wy, z) * aim((1.0, 0.0, 0.0)) * microscope_body(), "dummy")
    return out
