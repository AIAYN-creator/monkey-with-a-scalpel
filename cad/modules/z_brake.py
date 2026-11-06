"""Friction nut holder for the Z screw (card mech-z): a split block that preloads the plastic nut on the T8 screw, so the Z axis
does not back-drive with the power off even if the nut-to-screw friction is low. Not placed in the assembly: the linkage of
the nut to the Z carriage is not designed yet (the holder is the first part of it).

The motor of Z (dual shaft) and its hand wheel stay as they are; an electromagnetic brake on the rear shaft is the plan B if
the physical test (S7) shows the axis dropping.
"""
import params as P
from build123d import Box, Cylinder, Pos
from parts import hd, hole

BLOCK = (30.0, 24.0, 22.0)  # x, y, z


def z_nut_holder():
    """Block with a bore for the nut body (NUT_BORE) along Z, a slit and an M3 clamp screw that squeezes the nut onto the
    screw, and two M3 holes that fix it to the Z carriage plate. Floor at z = 0."""
    part = Pos(0, 0, BLOCK[2] / 2) * Box(*BLOCK)
    part -= Pos(0, 0, BLOCK[2] / 2) * Cylinder((P.NUT_BORE + P.HOLE_COMP) / 2, BLOCK[2] + 2)
    part -= Pos(0, BLOCK[1] / 4 + 1.0, BLOCK[2] / 2) * Box(1.2, BLOCK[1] / 2, BLOCK[2] + 2)  # slit on the +Y side
    part -= hole("x", hd(P.M3_CLEAR), BLOCK[0] + 2, 0, BLOCK[1] / 2 - 4.0, BLOCK[2] / 2)  # clamp screw across the slit
    for y in (-8.0, 0.0, 8.0)[::2]:
        part -= hole("z", hd(P.M3_CLEAR), BLOCK[2] + 2, 11.0, y, BLOCK[2] / 2)
    return part


PARTS = {"z_nut_holder": (z_nut_holder, "printed")}
