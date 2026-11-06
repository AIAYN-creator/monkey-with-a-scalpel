"""Contact probe (card t-probe): a spring stylus with a trigger switch, to find the surface, the bregma and the lambda.

Printed: the holder (5 mm bore, a flexure slot so the stylus gives way before it can push with more than the stop force) and the
switch bracket. Bought, as dummies: the stylus (a 1 mm rod) and a micro switch. Not placed in the machine assembly (see _toolkit.py).
"""
from build123d import Box, Pos

from ._toolkit import block, rod, sleeve

TOOL = {"name": "probe", "tip_z": -20.0, "dummy_mass_g": {"probe_stylus": 2.0, "probe_switch": 2.0}}


def probe_holder():
    part = sleeve(5.0)
    return part - Pos(0, 0, 11.0) * Box(40.0, 2.0, 4.0)  # the flexure slot across the block


def probe_switch_bracket():
    """Small bracket for the trigger switch, behind the stylus: a 20 x 8 x 4 mm foot and a 2 mm wall."""
    return Pos(0, 0, 2.0) * Box(20.0, 8.0, 4.0) + Pos(0, -3.0, 9.0) * Box(20.0, 2.0, 10.0)


PARTS = {"probe_holder": (probe_holder, "printed"), "probe_switch_bracket": (probe_switch_bracket, "printed")}
TOOL_ALLOWED = set()


def assembly():
    return {
        "probe_holder": (probe_holder(), "printed"),
        "probe_switch_bracket": (Pos(0, 8.0, 24.0) * probe_switch_bracket(), "printed"),
        "probe_stylus": (rod(1.0, -20.0, 40.0), "dummy"),
        "probe_switch": (block(0, 8.0, 34.0, (6.0, 3.5, 10.0)), "dummy"),
    }
