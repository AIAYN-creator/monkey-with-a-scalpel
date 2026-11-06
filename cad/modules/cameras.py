"""Cameras A (oblique, from the front) and B (lateral, horizontal) with their posts and mounts."""
import math

import parts
import system_parts as SP
from build123d import Pos, Rot
from layout import aim, camera_layout

PARTS = {
    "camera_wedge_45": (lambda: SP.camera_wedge(45), "printed"),
    "camera_plate": (parts.camera_plate, "printed"),
}


def fixed(variant, setback):
    out = {}
    cams = camera_layout(variant, setback)
    a = cams["A"]
    cx, cy, cz = a["centre"]
    pitch = a["pitch"]
    cp, sp_ = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    tilt_y, tilt_z = cy + cp * 22.5, cz + sp_ * 22.5
    flat_y = tilt_y + 8.0 + 20.0 * math.tan(math.radians(pitch))
    out["cam_a_post"] = (Pos(0, flat_y + 10.0, 0) * SP.profile(cz + 40.0), "purchased")
    out["cam_a_wedge"] = (Pos(0, flat_y, tilt_z) * Rot(0, 0, 180) * SP.camera_wedge(pitch), "printed")
    out["cam_a"] = (Pos(cx, cy, cz) * aim((0.0, -cp, -sp_)) * SP.camera_body(), "dummy")
    bx, by, bz = cams["B"]["centre"]
    out["cam_b_post"] = (Pos(bx + 22.5 + 5.0 + 10.0, by, 0) * SP.profile(120.0), "purchased")
    out["cam_b_plate"] = (Pos(bx + 22.5 + 5.0, by, bz) * Rot(0, 0, 90) * parts.camera_plate(), "printed")
    out["cam_b"] = (Pos(bx, by, bz) * aim((-1.0, 0.0, 0.0)) * SP.camera_body(), "dummy")
    return out
