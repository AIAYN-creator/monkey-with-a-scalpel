"""Specimen fixture: holds a test piece (a head-sized specimen, FIX_W wide) on the heater plate, as an alternative to the
phantom block. A V block under the piece and two lateral clamp posts with an M4 adjuster each.

Not part of the default assembly: the registry only places the phantom. `placed(variant, setback)` gives the placement for the
checks that swap the phantom for the fixture. Generic names on purpose: the public repository covers inert test pieces only.
All dimensions are assumed.
"""
import params as P
from build123d import Box, Pos, Rot
from layout import work_y
from parts import hd, hole

VB_X, VB_Y, VB_Z = 40.0, 50.0, 20.0  # V block
POST = (10.0, 14.0, 24.0)  # clamp post, low so the yoke arms of the wrist clear it


def specimen_vblock():
    """V block with a 90 degree groove along Y that centres the test piece; two M5 holes to the tray. Floor at z = 0."""
    part = Pos(0, 0, VB_Z / 2) * Box(VB_X, VB_Y, VB_Z)
    groove = Pos(0, 0, VB_Z + 2.0) * Rot(0, 45, 0) * Box(20.0, VB_Y + 2, 20.0)
    part -= groove
    for y in (-18.0, 18.0):
        part -= hole("z", hd(P.M5_CLEAR), VB_Z + 2, 0, y, VB_Z / 2)
    return part


def specimen_clamp_post():
    """Clamp post with a horizontal M4 adjuster that pushes a pad against the test piece. Floor at z = 0, adjuster along X."""
    part = Pos(0, 0, POST[2] / 2) * Box(*POST)
    part -= hole("x", hd(P.M4_CLEAR), POST[0] + 2, 0, 0, 14.0)
    part -= hole("z", hd(P.M5_CLEAR), POST[2] + 2, 0, 0, POST[2] / 2)  # foot screw
    return part


PARTS = {
    "specimen_vblock": (specimen_vblock, "printed"),
    "specimen_clamp_post": (specimen_clamp_post, "printed"),
}


def placed(variant, setback):
    """Placement on the tray for the swap checks (not used by the registry)."""
    wy = work_y(variant, setback)
    z0 = P.HEATER_T + 8.0  # tray top
    out = {"specimen_vblock": (Pos(0, wy, z0) * specimen_vblock(), "printed")}
    for sign in (-1, 1):
        x = sign * (P.FIX_W / 2 + POST[0] / 2)  # the post touches the piece; the adjuster only takes up the play
        out[f"specimen_clamp_post_{'r' if sign > 0 else 'l'}"] = (Pos(x, wy, z0) * specimen_clamp_post(), "printed")
    return out
