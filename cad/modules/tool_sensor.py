"""Optical sensor (card t-sense): a fibre ferrule with a shroud, to read fluorescence and photometry at the working point.

Printed: the holder (9 mm bore for the ferrule) and a shroud (a short tube that keeps stray light out). Bought, as dummies: the fibre
with its ferrule and a small board with the light source and the detector. Not placed in the machine assembly (see _toolkit.py).
"""
from build123d import Pos

from ._toolkit import block, ring, rod, sleeve

TOOL = {"name": "sensor", "tip_z": -15.0, "dummy_mass_g": {"sensor_fibre": 3.0, "sensor_board": 12.0}}


def sensor_holder():
    return sleeve(9.0)


def sensor_shroud():
    """Short tube around the fibre end: 16 mm outside, 9.4 mm inside, 14 mm long. Local frame: from z = 0 to 14."""
    return ring(16.0, 9.4, 14.0)


PARTS = {"sensor_holder": (sensor_holder, "printed"), "sensor_shroud": (sensor_shroud, "printed")}
TOOL_ALLOWED = set()


def assembly():
    return {
        "sensor_holder": (sensor_holder(), "printed"),
        "sensor_shroud": (Pos(0, 0, -16.0) * sensor_shroud(), "printed"),
        "sensor_fibre": (rod(9.0, -15.0, 60.0), "dummy"),
        "sensor_board": (block(0, 2.0, 75.0, (20.0, 6.0, 20.0)), "dummy"),
    }
