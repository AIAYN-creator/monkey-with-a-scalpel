"""Axis A of the wrist (card mech-wrist-2): the rotation about Y of the whole wrist, through the hub axis.

Names follow the firmware: B is the rotation about X (the cradle, wrist.py and wrist_drive.py), A the rotation about Y. A is the outer
axis: the yoke, the cradle, the B drive and the tool all turn with it, about the line along Y through the needle hub, so the tip
stays where it is to first order.

The stage is a fixed printed plate on the Z carriage plate with a boss for the bearing; the yoke plate turns on it with a gap of
A_GAP (14 mm, in layout.py) that the plate and the boss fill. The drive of A is a concept, not geometry: a single-start worm on an
arc of about 110 teeth around the yoke plate (module 1, pitch radius 55 mm), which gives about 489 steps per degree at 1/8 microstepping.
The worm has to sit outside the swept volume of the yoke plate, which needs a motor mount that reaches round it; that mount is the
open part of this card. Only present in the "wrist" variant.
"""
import params as P
from build123d import Box, Cylinder, Pos, Rot
from layout import A_GAP
from parts import hd, hole


def wrist_a_base():
    """Plate on the Z carriage plate that carries the bearing boss of axis A. Local frame: the A axis along Y through the origin, the
    plate behind the origin (y from -8 to -2 ... see the placement), 70 x 125 like the yoke plate, z from -17 to 108."""
    plate = Pos(0, 0, 45.5) * Box(70.0, 6.0, 125.0)  # z from -17 to 108
    boss = Pos(0, 5.0, 0) * Rot(90, 0, 0) * Cylinder(15.0, A_GAP - 4.0)  # bearing seat on the axis
    part = plate + boss
    part -= hole("y", hd(8.0), 30.0, 0, 3.0, 0)  # the axis bolt
    for x in (-20.0, 20.0):
        part -= hole("y", hd(P.M3_CLEAR), 10.0, x, 0, 100.0)  # to the carriage plate
    return part


PARTS = {"wrist_a_base": (wrist_a_base, "printed")}


def moving(pose):
    if pose.variant != "wrist":
        return {}
    face = pose.y_car  # front face of the Z carriage plate, whose plate is 6 mm thick
    frame = Pos(pose.xc, face + 6.0 + 3.0, pose.zh)  # the base plate sits against the carriage plate
    return {"wrist_a_base": (frame * wrist_a_base(), "printed", "z")}
