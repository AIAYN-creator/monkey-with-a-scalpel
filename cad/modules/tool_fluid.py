"""Fluid tool (card t-fluid): suction, irrigation and adhesive through two nozzles, with the pumps off the head.

Printed: the manifold (a block with the first nozzle seat in its bore) and the tube clip that keeps the tubing against the backplate.
Bought, as dummies: two nozzles (1.2 mm) and two tubes (3 mm). The second nozzle runs beside the block. Not placed in the machine
assembly (see _toolkit.py). The pumps and the valve are on the base and are not drawn.
"""
from build123d import Box, Cylinder, Pos

from ._toolkit import rod, sleeve

TOOL = {"name": "fluid", "tip_z": -25.0, "dummy_mass_g": {"fluid_nozzle_a": 1.0, "fluid_nozzle_b": 1.0, "fluid_tube_a": 6.0, "fluid_tube_b": 6.0}}


def fluid_manifold():
    return sleeve(1.4, z0=-2.0, z1=22.0)


def fluid_tube_clip():
    """Clip that holds the two tubes: 20 x 8 x 14 mm with two 3.4 mm holes the tubes pass through."""
    part = Pos(0, 0, 7.0) * Box(20.0, 8.0, 14.0)
    return part - Pos(-5.0, 0, 7.0) * Cylinder(1.7, 16.0) - Pos(5.0, 0, 7.0) * Cylinder(1.7, 16.0)


PARTS = {"fluid_manifold": (fluid_manifold, "printed"), "fluid_tube_clip": (fluid_tube_clip, "printed")}
TOOL_ALLOWED = {frozenset(("fluid_nozzle_a", "fluid_tube_a")), frozenset(("fluid_nozzle_b", "fluid_tube_b"))}


def assembly():
    return {
        "fluid_manifold": (fluid_manifold(), "printed"),
        "fluid_tube_clip": (Pos(0, 10.0, 30.0) * fluid_tube_clip(), "printed"),
        "fluid_nozzle_a": (rod(1.2, -25.0, 0.0), "dummy"),
        "fluid_nozzle_b": (rod(1.2, -25.0, -3.0, x=-12.0, y=-4.0), "dummy"),
        "fluid_tube_a": (rod(3.0, 25.0, 90.0, x=-5.0, y=10.0), "dummy"),
        "fluid_tube_b": (rod(3.0, 25.0, 90.0, x=5.0, y=10.0), "dummy"),
    }
