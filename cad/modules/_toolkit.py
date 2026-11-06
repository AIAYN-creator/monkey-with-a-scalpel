"""Shared pieces of the tool modules (files that start with an underscore are not modules of the registry).

A tool is drawn in the tool frame of cad/parts.py: the tool axis is Z through the origin, the needle hub plane of the injector is z = 0,
the tool points to -Z, and the backplate stands behind it (its front face is the plane y = -14). Every tool module has

    TOOL      {"name": the folder in tools/, "tip_z": z of the working point, "dummy_mass_g": {item: grams}}
    PARTS     the printed parts of the tool (names start with the tool name, so they never clash)
    assembly() -> {name: (shape, kind)} the tool in the tool frame, with dummies for what is bought

`cad/tool_check.py` checks each of them: valid solids, no unplanned overlaps, the working point where the descriptor says, inside the
envelope of the injector head, and the mass under the descriptor's. Tools are alternatives mounted one at a time, so they are not
placed in the machine assembly; the geometric sweeps of the build use the injector head, and the envelope check says the others fit
in it. The measurements are assumptions until the parts are bought (cards meas-tools and rev-tools).
"""
import params as P
from build123d import Box, Cylinder, Pos
from parts import hd, hole

FRONT = -14.0  # front face of the backplate


def sleeve(bore_d, z0=-2.0, z1=24.0, width=36.0, depth=30.0):
    """Block that bolts to the front of the backplate with the clamp pattern (M3 at x = +-15, z = 3 and 15) and holds the tool along Z
    through a bore of bore_d. The back face is at y = -14."""
    block = Pos(0, FRONT + depth / 2, (z0 + z1) / 2) * Box(width, depth, z1 - z0)
    block -= Pos(0, 0, (z0 + z1) / 2) * Cylinder(bore_d / 2, z1 - z0 + 2)
    for x in (-15.0, 15.0):
        for z in (3.0, 15.0):
            block -= hole("y", hd(P.M3_CLEAR), 20.0, x, FRONT + 4.0, z)
    return block


def ring(od, id_, height):
    """A tube along Z from z = 0 to height."""
    return Pos(0, 0, height / 2) * (Cylinder(od / 2, height) - Cylinder(id_ / 2, height + 2))


def rod(diameter, z_low, z_high, x=0.0, y=0.0):
    """A dummy cylinder along Z from z_low to z_high."""
    return Pos(x, y, (z_low + z_high) / 2) * Cylinder(diameter / 2, z_high - z_low)


def block(x, y, z, size):
    """A dummy box of size (sx, sy, sz) centred on (x, y, z)."""
    return Pos(x, y, z) * Box(*size)
