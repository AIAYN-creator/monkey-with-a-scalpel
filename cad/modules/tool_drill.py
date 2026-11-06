"""Micro-drill (card t-drill): a 20 mm micromotor in a split clamp with a depth-stop ring.

Printed: the clamp (a slit lets it close on the motor body) and the depth stop (a ring that bears on the skull surface and lets the bit
stand out 0 to 3 mm). Bought, as dummies: the micromotor (20 mm, 70 mm long, 2 A at most through the hardware cut-off), the bit (0.8 mm).
Not placed in the machine assembly (see _toolkit.py). The power of this tool goes through a hardware cut-off and is cut as the abort
starts (descriptor and firmware table).
"""
from build123d import Box, Pos

from ._toolkit import ring, rod, sleeve

TOOL = {"name": "drill", "tip_z": -30.0, "dummy_mass_g": {"drill_motor": 85.0, "drill_bit": 0.5}}


def drill_clamp():
    part = sleeve(20.0, z0=-2.0, z1=40.0)
    return part - Pos(0, 12.0, 19.0) * Box(2.0, 24.0, 44.0)  # the slit that lets the clamp close on the motor


def drill_depth_stop():
    """Ring 24 mm outside, 3.2 mm bore for the bit, 8 mm high. Local frame: from z = 0 to 8."""
    return ring(24.0, 3.2, 8.0)


PARTS = {"drill_clamp": (drill_clamp, "printed"), "drill_depth_stop": (drill_depth_stop, "printed")}
TOOL_ALLOWED = {frozenset(("drill_motor", "drill_bit"))}


def assembly():
    return {
        "drill_clamp": (drill_clamp(), "printed"),
        "drill_motor": (rod(19.6, 0.0, 70.0), "dummy"),
        "drill_bit": (rod(0.8, -30.0, 0.5), "dummy"),
        "drill_depth_stop": (Pos(0, 0, -12.0) * drill_depth_stop(), "printed"),
    }
