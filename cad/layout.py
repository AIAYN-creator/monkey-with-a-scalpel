"""Shared layout of the system: constants and placement helpers used by system.py and by every module.

Nothing here builds a part. The world frame is the one of system.py: origin on the top face of the base plate, below the
crossbeam; X to the right, Y towards the user, Z up.
"""
import math
from dataclasses import dataclass

import params as P
from build123d import Rot

HUB_TO_CARRIAGE = 93.0  # z of the carriage centre above the needle hub plane (interface at 60 + 33)
Z_PATTERN = 265.0  # world z of the Z plate pattern centre
Z_PLATE_LEN = 200.0
Z_PLATE_PATTERN_X = 75.0
Z_PLATE_CENTRE = Z_PATTERN - Z_PLATE_PATTERN_X
CARRIAGE_Z_MIN = P.TIP_MIN + 30.0 + HUB_TO_CARRIAGE  # needle tip lowest
CARRIAGE_Z_MAX = CARRIAGE_Z_MIN + P.TRAVEL
HALF = P.TRAVEL / 2


def y_carriage_face(yc):
    """World y of the face of the Z carriage (where the printed carriage plate starts)."""
    return yc + P.ARM_REACH + 3.0 + 6.0 + P.CARR_H


def y_axis(yc, variant, setback):
    """World y of the needle axis."""
    face = y_carriage_face(yc)
    return face + (26.0 if variant == "fixed" else setback + 12.0)


def work_y(variant, setback):
    return y_axis(0.0, variant, setback)


def aim(direction):
    """Rotation that takes +Z to `direction`."""
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    return Rot(0, 0, math.degrees(math.atan2(dy, dx))) * Rot(0, math.degrees(math.acos(dz / length)), 0)


def camera_layout(variant, setback):
    """Positions of the two cameras (centres) and the pitch of the oblique one."""
    wy = work_y(variant, setback)
    pitch = 40.0
    return {
        "A": {"centre": (0.0, wy + 95.0, 135.0), "pitch": pitch},
        "B": {"centre": (152.5, wy, 45.0)},
    }


@dataclass(frozen=True)
class Pose:
    """Where the moving parts are: the axis positions, the wrist angle and the variant of the assembly."""

    variant: str = "fixed"
    xc: float = 0.0
    yc: float = 0.0
    zc: float = CARRIAGE_Z_MIN + HALF
    theta: float = 0.0
    setback: float = 110.0

    @property
    def y_car(self):
        """World y of the face of the Z carriage."""
        return y_carriage_face(self.yc)

    @property
    def y_pf(self):
        """Front face of the Z plate."""
        return self.y_car - P.CARR_H

    @property
    def y_leg(self):
        """Front face of the riser leg."""
        return self.yc + P.ARM_REACH + 3.0

    @property
    def yax(self):
        """World y of the needle axis."""
        return y_axis(self.yc, self.variant, self.setback)

    @property
    def zh(self):
        """World z of the needle hub plane."""
        return self.zc - HUB_TO_CARRIAGE

    @property
    def y_seat(self):
        """World z of the seat of the Y rail (on the Y plate)."""
        return P.CROSSBEAM_TOP + P.CARR_H + 6.0
