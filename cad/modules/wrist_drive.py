"""Drive of the wrist tilt axis (card mech-wrist): a worm and a printed sector gear on the pivot, with a NEMA 11 on the yoke.

The sector is fixed to the cradle (it rotates with the tool) on the outside of the right yoke arm; the worm, its motor and the
mount stay on the yoke. These are envelopes: the teeth, the bearings of the worm and the coupler are not drawn. The tilt axis
drawn here is the rotation about X (the one the CAD already has); the second wrist axis (rotation about Y) is a concept, not
geometry. Only present in the "wrist" variant.
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
WORM_D, WORM_L = 10.0, 36.0
WORM_X = 41.0  # worm and motor axis: 2 mm outside the middle of the sector so the motor clears the cradle at +30 degrees
WORM_Z = SECTOR_R + 4.0  # worm axis height: the rim of the sector minus the tooth depth plus the worm radius
MOTOR = (28.2, 32.0, 28.2)  # NEMA 11 envelope: x, y, z
MOTOR_Y = -43.0  # centre; its front face is 27 mm behind the pivot plane so it clears the cradle plate and the mount wall


def wrist_sector_a():
    """Sector of 80 degrees and 40 mm radius, 6 mm thick, with the 8 mm pivot bore. Local frame: the pivot axis along X
    through the origin (the thickness from x = 0 to 6), the sector pointing up (+Z)."""
    points = [(0.0, 0.0)]
    for k in range(-8, 9):
        a = math.radians(SECTOR_ARC * k / 8)
        points.append((SECTOR_R * math.sin(a), SECTOR_R * math.cos(a)))
    with BuildPart() as sector:
        with BuildSketch(Plane.YZ):
            Polygon(*points, align=None)
        extrude(amount=SECTOR_X[1] - SECTOR_X[0])
    part = sector.part
    part -= hole("x", hd(8.0), 10.0, 3.0, 0, 0)
    return part


def wrist_motor_mount_a():
    """Wall that stands on the top of the right yoke arm and carries the bearings of the worm (not detailed). Local frame:
    its underside at z = 0, x from 0 to 6, two vertical M3 pilot holes in the underside."""
    wall = Pos(3.0, 1.0, 18.0) * Box(6.0, 42.0, 36.0)
    for y in (-14.0, 16.0):
        wall -= hole("z", hd(P.M3_CLEAR), 8.0, 3.0, y, 4.0)
    return wall


PARTS = {
    "wrist_sector_a": (wrist_sector_a, "printed"),
    "wrist_motor_mount_a": (wrist_motor_mount_a, "printed"),
}
ALLOWED = {frozenset(("wrist_sector_a", "wrist_worm_a"))}


def moving(pose):
    if pose.variant != "wrist":
        return {}
    frame = Pos(pose.xc, pose.yax, pose.zh)
    tool_frame = frame * Rot(pose.theta, 0, 0)
    x_mid = WORM_X
    out = {"wrist_sector_a": (tool_frame * Pos(SECTOR_X[0], 0, 0) * wrist_sector_a(), "printed", "tool")}
    out["wrist_worm_a"] = (frame * Pos(x_mid, 0, WORM_Z) * Rot(90, 0, 0) * Cylinder(WORM_D / 2, WORM_L), "dummy", "z")
    out["wrist_motor_a"] = (frame * Pos(x_mid, MOTOR_Y, WORM_Z) * Box(*MOTOR), "dummy", "z")
    out["wrist_motor_mount_a"] = (frame * Pos(27.0, 0, 17.0) * wrist_motor_mount_a(), "printed", "z")
    return out
