"""Active wrist (A axis, tilt about X, pivot at the needle hub plane): the fixed yoke and the moving cradle.

Only present in the "wrist" variant of the assembly.
"""
import params as P
from build123d import Box, Pos, Rot
from parts import hd, hole, interface_cut

DEFAULT_SETBACK = 110.0  # mm, from the swing search: 100 is the smallest that clears at 30 degrees


def wrist_yoke(setback):
    """Fixed part of the active wrist (A axis, tilt about X). Tool frame: pivot axis through the origin, along X.

    Back plate against the Z carriage plate, two arms to the pivot with a 608 bearing pocket each.
    `setback` is the distance from the pivot axis to the front face of the back plate.
    """
    plate_y0, plate_y1 = -(setback + 6.0), -setback
    plate = Pos(0, (plate_y0 + plate_y1) / 2, 45.5) * Box(70, 6, 125)  # z from -17 to 108
    part = plate
    for sign in (-1, 1):
        arm = Pos(sign * 31.0, (plate_y0 + 8.0) / 2, 0) * Box(8, 8.0 - plate_y0, 34)  # x from 27 to 35
        part += arm
        part -= hole("x", P.BEARING_OD + P.HOLE_COMP, P.BEARING_W, sign * (35.0 - P.BEARING_W / 2), 0, 0)
        part -= hole("x", hd(9.0), 12, sign * 31.0, 0, 0)
    part -= interface_cut(z0=60.0, y0=(plate_y0 + plate_y1) / 2, length=20)
    return part


def wrist_cradle():
    """Moving part of the active wrist: plate behind the tool backplate, two cheeks that carry the pivot bolts."""
    plate = Pos(0, -23.0, 59.0) * Box(52, 6, 102)  # y from -26 to -20, z from 8 to 110
    part = plate
    for sign in (-1, 1):
        part += Pos(sign * 23.0, -9.0, 0) * Box(6, 34, 16)  # y from -26 to 8
        part -= hole("x", hd(8.0), 10, sign * 23.0, 0, 0)
    part -= interface_cut(z0=60.0, y0=-23.0, length=20)
    return part


PARTS = {
    "wrist_cradle": (wrist_cradle, "printed"),
    "wrist_yoke": (lambda: wrist_yoke(DEFAULT_SETBACK), "printed"),
}

_CRADLE = []


def moving(pose):
    if pose.variant != "wrist":
        return {}
    if not _CRADLE:
        _CRADLE.append(wrist_cradle())
    out = {"wrist_yoke": (Pos(pose.xc, pose.yax, pose.zh) * wrist_yoke(pose.setback), "printed", "z")}
    tool_frame = Pos(pose.xc, pose.yax, pose.zh) * Rot(pose.theta, 0, 0)
    out["wrist_cradle"] = (tool_frame * _CRADLE[0], "printed", "tool")
    return out
