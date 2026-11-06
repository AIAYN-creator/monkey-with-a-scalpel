"""Drive of the wrist tilt axis B (rotation about X): a worm and a split printed sector on the pivot, with a NEMA 11 on the yoke.

Axis names follow the firmware and the simulation: B is the rotation about X (the inner axis, the one this CAD has), A is the
rotation about Y (the outer axis, not designed yet: card mech-wrist-2).

Why a worm: it is self-locking, so with the power off the tool keeps its tilt instead of swinging into the work area, it holds the
angle while the needle is inserted (dec-arq asks for the wrist to be lockable then), it is compact and it prints. The cost is
backlash, which the split sector reduces: two 3 mm layers, the rear one pushed round a little by springs so both flanks of the worm
teeth stay in contact. A belt would have less backlash but does not self-lock; a spur sector does not either.

The sector is fixed to the cradle (it rotates with the tool) on the outside of the right yoke arm; the worm, its motor and the
mount stay on the yoke. These are envelopes: the teeth, the springs, the bearings of the worm and the coupler are not drawn.
Only present in the "wrist" variant.
"""
import math

import params as P
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    Rot,
    extrude,
)
from parts import hd, hole

SECTOR_R = 40.0  # pitch radius of the sector, mm
SECTOR_ARC = 40.0  # half arc, degrees (the wrist travels +-WRIST_MAX, 30)
SECTOR_X = (36.0, 42.0)  # outside the right yoke arm, which spans x 27 to 35
LAYER = (SECTOR_X[1] - SECTOR_X[0]) / 2  # thickness of each layer of the split sector
SPRING_R = 30.0  # radius of the spring pins and of their arc slots
TEETH = 80  # teeth of the sector (module 1)
WORM_D, WORM_L = 10.0, 36.0
WORM_X = 41.0  # worm and motor axis: 2 mm outside the middle of the sector so the motor clears the cradle at +30 degrees
WORM_Z = SECTOR_R + 4.0  # worm axis height: the rim of the sector minus the tooth depth plus the worm radius
MOTOR = (28.2, 32.0, 28.2)  # NEMA 11 envelope: x, y, z
MOTOR_Y = -43.0  # centre; its front face is 27 mm behind the pivot plane so it clears the cradle plate and the mount wall

# resolution of the drive (hand calculation): single-start worm on the sector, NEMA 11 at 1/8 microstepping
MICROSTEPS_PER_REV = 200 * 8
STEPS_PER_DEGREE = MICROSTEPS_PER_REV * TEETH / 360.0  # about 355.6


def _sector_layer(rear):
    points = [(0.0, 0.0)]
    for k in range(-8, 9):
        a = math.radians(SECTOR_ARC * k / 8)
        points.append((SECTOR_R * math.sin(a), SECTOR_R * math.cos(a)))
    with BuildPart() as sector:
        with BuildSketch(Plane.YZ):
            Polygon(*points, align=None)
        extrude(amount=LAYER)
    part = sector.part
    part -= hole("x", hd(8.0), 10.0, LAYER / 2, 0, 0)  # pivot bore
    for angle in (-12.0, 12.0):  # a spring pin in the front layer and, in the rear layer, an arc slot around it
        if rear:
            for k in range(-2, 3):  # a slot 3.4 mm wide and about 8 degrees long, drawn as five overlapping holes
                b = math.radians(angle + 2.0 * k)
                part -= hole("x", 3.4, 10.0, LAYER / 2, SPRING_R * math.sin(b), SPRING_R * math.cos(b))
        else:
            a = math.radians(angle)
            part -= hole("x", 3.0, 10.0, LAYER / 2, SPRING_R * math.sin(a), SPRING_R * math.cos(a))  # pin hole
    return part


def wrist_sector_b_front():
    """Front layer of the split sector (3 mm, 80 degrees, radius 40, 8 mm pivot bore, two 3 mm spring-pin holes). Local frame: the
    pivot axis along X through the origin, the thickness from x = 0 to 3, the sector pointing up (+Z)."""
    return _sector_layer(rear=False)


def wrist_sector_b_rear():
    """Rear layer of the split sector: the same outline with an arc slot around each spring pin, so it can turn a few degrees
    against the front layer and take up the backlash. Same local frame."""
    return _sector_layer(rear=True)


def wrist_motor_mount_b():
    """Wall that stands on the top of the right yoke arm and carries the bearings of the worm (not detailed). Local frame:
    its underside at z = 0, x from 0 to 6, two vertical M3 pilot holes in the underside."""
    wall = Pos(3.0, 1.0, 18.0) * Box(6.0, 42.0, 36.0)
    for y in (-14.0, 16.0):
        wall -= hole("z", hd(P.M3_CLEAR), 8.0, 3.0, y, 4.0)
    return wall


PARTS = {
    "wrist_sector_b_front": (wrist_sector_b_front, "printed"),
    "wrist_sector_b_rear": (wrist_sector_b_rear, "printed"),
    "wrist_motor_mount_b": (wrist_motor_mount_b, "printed"),
}
ALLOWED = {
    frozenset(("wrist_sector_b_front", "wrist_worm_b")),
    frozenset(("wrist_sector_b_rear", "wrist_worm_b")),
}


def moving(pose):
    if pose.variant != "wrist":
        return {}
    frame = Pos(pose.xc, pose.yax, pose.zh) * Rot(0, pose.phi, 0)  # the drive of B turns with A
    tool_frame = frame * Rot(pose.theta, 0, 0)
    out = {
        "wrist_sector_b_front": (tool_frame * Pos(SECTOR_X[0], 0, 0) * wrist_sector_b_front(), "printed", "tool"),
        "wrist_sector_b_rear": (tool_frame * Pos(SECTOR_X[0] + LAYER, 0, 0) * wrist_sector_b_rear(), "printed", "tool"),
    }
    out["wrist_worm_b"] = (frame * Pos(WORM_X, 0, WORM_Z) * Rot(90, 0, 0) * Cylinder(WORM_D / 2, WORM_L), "dummy", "tool")
    out["wrist_motor_b"] = (frame * Pos(WORM_X, MOTOR_Y, WORM_Z) * Box(*MOTOR), "dummy", "tool")
    out["wrist_motor_mount_b"] = (frame * Pos(27.0, 0, 17.0) * wrist_motor_mount_b(), "printed", "tool")
    return out
