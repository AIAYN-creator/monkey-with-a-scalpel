"""Scalpel tool (card t-scalpel): a blade holder with a depth-stop collar and a guard that a spring closes.

Printed: the holder (bolts to the backplate, 7 mm bore), the guard (a tube that covers the blade; a small servo or solenoid opens it, a
spring closes it, so with the power off the guard is closed) and the depth collar (a ring that clamps on the stem and sets how far the
blade can go; the model in host/toolsim refuses a cut deeper than the stop). Bought, as dummies: the blade (a #11 style blade, 0.4 mm
thick) and its stem, and the guard servo. Alternative to the other tools: not placed in the machine assembly (see _toolkit.py).
"""
from build123d import Pos

from ._toolkit import block, ring, rod, sleeve

TOOL = {"name": "scalpel", "tip_z": -25.0, "dummy_mass_g": {"scalpel_stem": 12.0, "scalpel_blade": 1.0, "scalpel_guard_servo": 9.0}}


def scalpel_holder():
    return sleeve(7.0)


def scalpel_guard():
    """Tube that covers the blade when closed: 14 mm outside, 8 mm inside, 27 mm long. Local frame: from z = 0 to 27."""
    return ring(14.0, 8.0, 27.0)


def scalpel_depth_collar():
    """Ring that clamps on the stem (M3 grub screw not drawn) and stops against the holder: 16 mm outside, 6.2 mm inside, 6 mm high."""
    return ring(16.0, 6.2, 6.0)


PARTS = {
    "scalpel_holder": (scalpel_holder, "printed"),
    "scalpel_guard": (scalpel_guard, "printed"),
    "scalpel_depth_collar": (scalpel_depth_collar, "printed"),
}
TOOL_ALLOWED = {
    frozenset(("scalpel_stem", "scalpel_depth_collar")),
    frozenset(("scalpel_stem", "scalpel_blade")),
}


def assembly():
    return {
        "scalpel_holder": (scalpel_holder(), "printed"),
        "scalpel_guard": (Pos(0, 0, -30.0) * scalpel_guard(), "printed"),  # closed: covers the blade, from z = -30 to -3
        "scalpel_depth_collar": (Pos(0, 0, 30.0) * scalpel_depth_collar(), "printed"),
        "scalpel_stem": (rod(6.0, -14.0, 60.0), "dummy"),
        "scalpel_blade": (block(0, 0, -19.0, (6.0, 0.4, 12.0)), "dummy"),  # tip at z = -25
        "scalpel_guard_servo": (block(18.0, 2.0, 52.0, (22.0, 12.0, 23.0)), "dummy"),
    }
