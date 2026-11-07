"""Electronics: the printed tray and lid for the supply, contactor, drivers and ESP32, and the cable clips for the 2020 slot."""
import params as P
from build123d import Box, Cylinder, Pos, Rot
from parts import hd, hole

ENC_X, ENC_Y, ENC_Z, ENC_WALL = 210.0, 105.0, 85.0, 3.0


def cable_clip_2020():
    """Clip for the 6 mm slot of a 2020 profile with an open saddle for a cable bundle (about 12 mm).

    Local frame: z = 0 at the profile face, +z away from it; the stem and the T head go into the slot (-z).
    The slot dimensions are typical values to check on the real profile.
    """
    stem = Pos(0, 0, -3.0) * Box(5.6, 10.0, 6.0)
    head = Pos(0, 0, -7.0) * Box(10.2, 10.0, 2.0)
    saddle = Pos(0, 0, 8.0) * Box(20.0, 10.0, 16.0)
    part = stem + head + saddle
    part -= Pos(0, 0, 8.5) * Rot(90, 0, 0) * Cylinder(6.0, 12.0)
    part -= Pos(0, 0, 14.0) * Box(11.0, 12.0, 10.0)  # open top of the saddle
    return part


def electronics_enclosure():
    """Printed tray for the supply, contactor, drivers and ESP32, open on top (the lid screws into four posts).

    Local frame: centred on x and y, floor at z = 0. The rear wall (-y) carries eleven 12.2 mm holes for panel
    connectors or cable glands, one per cable of the wiring map (provisional size). Fixing to the base is not
    designed: four 4.4 mm holes in the floor, reachable with the lid off.
    """
    outer = Pos(0, 0, ENC_Z / 2) * Box(ENC_X, ENC_Y, ENC_Z)
    inner = Pos(0, 0, ENC_WALL + (ENC_Z - ENC_WALL) / 2 + 0.01) * Box(
        ENC_X - 2 * ENC_WALL, ENC_Y - 2 * ENC_WALL, ENC_Z - ENC_WALL)
    part = outer - inner
    px, py = ENC_X / 2 - ENC_WALL - 5.0, ENC_Y / 2 - ENC_WALL - 5.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            part += Pos(sx * px, sy * py, ENC_WALL + (ENC_Z - ENC_WALL) / 2) * Cylinder(4.0, ENC_Z - ENC_WALL)
            part -= hole("z", 2.5, 12.0, sx * px, sy * py, ENC_Z - 6.0)
    for i in range(11):
        part -= hole("y", 12.2 + P.HOLE_COMP, 10, -85.0 + 17.0 * i, -ENC_Y / 2 + ENC_WALL / 2, 45.0)
    for x in (-60.0, 60.0):
        for y in (-25.0, 25.0):
            part -= hole("z", hd(P.M4_CLEAR), 10, x, y, ENC_WALL / 2)
    return part


def enclosure_lid():
    """Lid of the electronics tray with vent slots and four M3 holes. Local frame: z = 0 at the underside."""
    part = Pos(0, 0, 1.5) * Box(ENC_X, ENC_Y, 3.0)
    px, py = ENC_X / 2 - ENC_WALL - 5.0, ENC_Y / 2 - ENC_WALL - 5.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            part -= hole("z", hd(P.M3_CLEAR), 10, sx * px, sy * py, 1.5)
    for i in range(8):
        part -= Pos(-70.0 + 20.0 * i, 0, 1.5) * Box(4.0, 40.0, 10.0)
    return part


PARTS = {
    "cable_clip_2020": (cable_clip_2020, "printed"),
    "electronics_enclosure": (electronics_enclosure, "printed"),
    "enclosure_lid": (enclosure_lid, "printed"),
}
# the stem of a cable clip sits in the slot of the profile, which the dummy profile does not have
ALLOWED = {
    frozenset(("upright_l", "cable_clip_upright_0")),
    frozenset(("upright_l", "cable_clip_upright_1")),
    frozenset(("upright_l", "cable_clip_upright_2")),
    frozenset(("crossbeam", "cable_clip_beam_0")),
    frozenset(("crossbeam", "cable_clip_beam_1")),
}


def fixed(variant, setback):
    out = {}
    out["electronics_enclosure"] = (Pos(0, -75.0, 0) * electronics_enclosure(), "printed")
    out["enclosure_lid"] = (Pos(0, -75.0, ENC_Z) * enclosure_lid(), "printed")
    for i, z in enumerate((60.0, 120.0, 180.0)):  # cable clips up the rear face of the left upright
        out[f"cable_clip_upright_{i}"] = (Pos(-P.UPRIGHT_X, -P.PROFILE / 2, z) * Rot(90, 0, 0) * cable_clip_2020(), "printed")
    for i, x in enumerate((-100.0, -50.0)):  # and along the rear face of the crossbeam
        out[f"cable_clip_beam_{i}"] = (
            Pos(x, -P.BEAM_W / 2 - 10.0, P.CROSSBEAM_TOP - 50.0) * Rot(90, 0, 0) * cable_clip_2020(), "printed")
    return out
