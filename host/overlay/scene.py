"""A simulated scene: two cameras and a microscope looking at a phantom block, and frames drawn from their projection matrices.

The cameras are pinhole cameras built with `look_at` (the matrices have the same form as the ones that `coords.fit_projection`
fits from a real calibration, so the overlay code does not care where a matrix comes from). The frames are synthetic: a dark
background, the phantom block as a lighter rectangle and the tool tip as a bright dot. Positions are in machine millimetres (X right,
Y towards the user, Z up).
"""
import numpy as np

WIDTH, HEIGHT = 640, 480


def look_at(position, target, focal_px, up=(0.0, 0.0, 1.0), size=(WIDTH, HEIGHT)):
    """3 x 4 projection matrix of a pinhole camera at `position` looking at `target`."""
    position = np.asarray(position, dtype=float)
    forward = np.asarray(target, dtype=float) - position
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, np.asarray(up, dtype=float))
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    rotation = np.vstack([right, down, forward])
    K = np.array([[focal_px, 0.0, size[0] / 2], [0.0, focal_px, size[1] / 2], [0.0, 0.0, 1.0]])
    return K @ np.hstack([rotation, (-rotation @ position)[:, None]])


def default_cameras(work_y=0.0):
    """Camera A in front and above, camera B on the right, the microscope on the left, all aimed at the phantom (as in the CAD)."""
    centre = np.array([0.0, work_y, 10.0])
    return {
        "A": look_at((0.0, work_y + 175.0, 170.0), centre, focal_px=1400.0),
        "B": look_at((152.5, work_y, 45.0), centre, focal_px=1100.0),
        "M": look_at((-100.0, work_y, 10.0), centre, focal_px=9000.0),  # the microscope: a long lens, a small field
    }


def _disc(image, centre, radius, colour):
    h, w, _ = image.shape
    cx, cy = centre
    x0, x1 = max(int(cx - radius) - 1, 0), min(int(cx + radius) + 2, w)
    y0, y1 = max(int(cy - radius) - 1, 0), min(int(cy + radius) + 2, h)
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
    image[y0:y1, x0:x1][mask] = colour


def render(P, tip, block_corners):
    """A synthetic frame (H x W x 3 uint8) of the phantom block (8 corners) and the tool tip."""
    from coords import (
        project,  # imported here so the scene can be used without the rest of the package
    )

    image = np.full((HEIGHT, WIDTH, 3), (16, 24, 38), dtype=np.uint8)
    pixels = np.atleast_2d(project(P, np.asarray(block_corners, dtype=float)))
    lo, hi = pixels.min(axis=0), pixels.max(axis=0)
    x0, y0 = int(max(lo[0], 0)), int(max(lo[1], 0))
    x1, y1 = int(min(hi[0], WIDTH)), int(min(hi[1], HEIGHT))
    if x0 < x1 and y0 < y1:
        image[y0:y1, x0:x1] = (60, 80, 104)
    _disc(image, project(P, np.asarray(tip, dtype=float)), 4.0, (235, 242, 248))
    return image


def block(centre, size=(40.0, 40.0, 20.0)):
    """The 8 corners of a box (the phantom) centred on `centre`."""
    cx, cy, cz = centre
    sx, sy, sz = (s / 2 for s in size)
    return [(cx + dx * sx, cy + dy * sy, cz + dz * sz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
