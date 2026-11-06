"""Sample frame: converts between machine coordinates and a frame defined by landmarks on the sample or phantom.

Machine frame: X to the right, Y towards the user, Z up, in millimetres (the frame of cad/system.py).

Sample frame (right-handed): AP towards the front of the sample (anterior), ML towards its right, DV towards its top
(dorsal). The origin is the first landmark. The second landmark lies behind the first one, so its AP coordinate is
negative. DV can be reported as depth (positive downwards) with `ventral_positive=True`.

A distance between landmarks that comes from a reference table is a prior, not a measurement: `check_spacing` compares it
with the measured one and says whether they agree, so a plan can never silently treat the table value as measured.
"""
from dataclasses import dataclass

import numpy as np


class FrameError(ValueError):
    """The landmarks cannot define a frame (coincident, collinear with the up direction, ...)."""


def _unit(vector, what):
    vector = np.asarray(vector, dtype=float)
    norm = np.linalg.norm(vector)
    if norm < 1e-9:
        raise FrameError(f"{what} has zero length")
    return vector / norm


@dataclass(frozen=True)
class SampleFrame:
    origin: np.ndarray  # machine coordinates of the origin landmark
    rotation: np.ndarray  # 3 x 3 proper rotation, columns are the ML, AP and DV axes in machine coordinates (right-handed)
    ventral_positive: bool = False
    pitch_deg: float = 0.0  # angle between the line of the landmarks and the horizontal, signed (nose up positive)

    @classmethod
    def from_landmarks(cls, origin, rear_point, up=(0.0, 0.0, 1.0), level=True, ventral_positive=False):
        """Frame from two landmarks: `origin` and `rear_point` (behind it), plus the up direction of the machine.

        With `level=True` the AP axis is the projection of the landmark line on the horizontal plane (the sample is
        assumed levelled and the tilt is only reported in `pitch_deg`); with `level=False` the AP axis follows the line.
        """
        origin = np.asarray(origin, dtype=float)
        rear_point = np.asarray(rear_point, dtype=float)
        up = _unit(up, "up")
        line = origin - rear_point
        _unit(line, "the line between the landmarks")
        horizontal = line - np.dot(line, up) * up
        pitch = float(np.degrees(np.arctan2(np.dot(line, up), np.linalg.norm(horizontal))))
        anterior = _unit(horizontal if level else line, "the landmark line seen from above" if level else "the landmark line")
        dorsal = up - np.dot(up, anterior) * anterior
        if np.linalg.norm(dorsal) < 1e-9:
            raise FrameError("the landmark line is parallel to the up direction")
        dorsal = dorsal / np.linalg.norm(dorsal)
        right = np.cross(anterior, dorsal)  # facing `anterior` with `dorsal` up, this is the sample's right
        return cls(origin, np.column_stack([right, anterior, dorsal]), ventral_positive, pitch)

    def to_sample(self, point):
        """(AP, ML, DV) of a machine point, in millimetres."""
        ml, ap, dv = self.rotation.T @ (np.asarray(point, dtype=float) - self.origin)
        return np.array([ap, ml, -dv if self.ventral_positive else dv])

    def to_machine(self, ap, ml, dv):
        """Machine coordinates of a sample point."""
        dv = -dv if self.ventral_positive else dv
        return self.origin + self.rotation @ np.array([ml, ap, dv], dtype=float)

    def direction_to_machine(self, ap, ml, dv):
        """Machine direction of a sample direction (no translation)."""
        dv = -dv if self.ventral_positive else dv
        return self.rotation @ np.array([ml, ap, dv], dtype=float)


def check_spacing(measured_mm, reference_mm, tolerance_mm):
    """Compares a measured landmark spacing with a reference value.

    Returns {"agrees": bool, "difference_mm": float}. The reference is a prior: when it does not agree, the plan has to
    say so and go on with the measured value.
    """
    difference = float(measured_mm - reference_mm)
    return {"agrees": abs(difference) <= tolerance_mm, "difference_mm": round(difference, 3)}
