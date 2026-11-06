"""Gripper (card t-grip): two jaws on a slide driven by the P axis, closed by a spring, for a fibre, an electrode or an implant.

Printed: the body (slide and bore) and two jaws (3 x 10 x 28 mm with a 1 mm groove for a fibre). Bought, as dummies: the actuator
(a small linear actuator or servo with a force limit). Not placed in the machine assembly (see _toolkit.py). With the power off or
after an abort the spring keeps the item held.
"""
from build123d import Box, Cylinder, Pos, Rot

from ._toolkit import block, sleeve

TOOL = {"name": "gripper", "tip_z": -30.0, "dummy_mass_g": {"gripper_actuator": 30.0}}


def gripper_body():
    return sleeve(8.0, z0=-2.0, z1=30.0)


def gripper_jaw():
    """Jaw 3 x 10 x 28 mm with a groove along its length for a 1 mm item. Local frame: the working face at x = 0, from z = 0 to 28."""
    jaw = Pos(1.5, 0, 14.0) * Box(3.0, 10.0, 28.0)
    return jaw - Pos(0, 0, 14.0) * Cylinder(0.5, 30.0)


PARTS = {"gripper_body": (gripper_body, "printed"), "gripper_jaw": (gripper_jaw, "printed")}
TOOL_ALLOWED = set()


def assembly():
    left = Pos(-1.0, 0, -30.0) * Rot(0, 0, 180) * gripper_jaw()  # closed: the faces are 2 mm apart; the jaws end at z = -30
    right = Pos(1.0, 0, -30.0) * gripper_jaw()
    return {
        "gripper_body": (gripper_body(), "printed"),
        "gripper_jaw_left": (left, "printed"),
        "gripper_jaw_right": (right, "printed"),
        "gripper_actuator": (block(0, 2.0, 50.0, (24.0, 12.0, 26.0)), "dummy"),
    }
