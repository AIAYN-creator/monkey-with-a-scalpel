"""Camera calibration and triangulation with numpy only.

A camera is a 3 x 4 projection matrix P that maps machine points (mm) to pixels. It is fitted from correspondences between
known machine points and their pixels (direct linear transform with Hartley normalisation), and two cameras give the 3D
position of a point (linear triangulation). Lens distortion is not modelled: undistort the images first.
"""
import numpy as np


class CalibrationError(ValueError):
    """Not enough or degenerate correspondences."""


def _normalise(points):
    """Similarity transform that centres the points and scales them to a mean distance of sqrt(dim)."""
    dim = points.shape[1]
    centre = points.mean(axis=0)
    scale = np.sqrt(dim) / max(np.mean(np.linalg.norm(points - centre, axis=1)), 1e-12)
    transform = np.eye(dim + 1)
    transform[:dim, :dim] *= scale
    transform[:dim, dim] = -scale * centre
    homogeneous = np.hstack([points, np.ones((len(points), 1))])
    return (transform @ homogeneous.T).T, transform


def project(P, points):
    """Pixels (N x 2) of machine points (N x 3), or (2,) for one point."""
    points = np.atleast_2d(np.asarray(points, dtype=float))
    homogeneous = np.hstack([points, np.ones((len(points), 1))]) @ np.asarray(P).T
    pixels = homogeneous[:, :2] / homogeneous[:, 2:3]
    return pixels if len(pixels) > 1 else pixels[0]


def reprojection_rms(P, points, pixels):
    """Root mean square distance in pixels between the projected points and the observed pixels."""
    points = np.atleast_2d(points)
    pixels = np.atleast_2d(pixels)
    return float(np.sqrt(np.mean(np.sum((np.atleast_2d(project(P, points)) - pixels) ** 2, axis=1))))


def fit_projection(points3d, pixels):
    """Projection matrix from at least 6 non-coplanar machine points and their pixels. Returns (P, rms_pixels)."""
    points3d = np.asarray(points3d, dtype=float)
    pixels = np.asarray(pixels, dtype=float)
    if len(points3d) < 6 or len(points3d) != len(pixels):
        raise CalibrationError("at least 6 matching points are needed")
    centred = points3d - points3d.mean(axis=0)
    if np.linalg.svd(centred, compute_uv=False)[2] < 1e-6 * np.linalg.svd(centred, compute_uv=False)[0]:
        raise CalibrationError("the points are coplanar: use fit_plane_homography or add points off the plane")
    X, Tx = _normalise(points3d)
    x, Tp = _normalise(pixels)
    rows = []
    for (a, b, c, d), (u, v, w) in zip(X, x, strict=True):
        rows.append([a, b, c, d, 0, 0, 0, 0, -u * a, -u * b, -u * c, -u * d])
        rows.append([0, 0, 0, 0, a, b, c, d, -v * a, -v * b, -v * c, -v * d])
    _, _, vt = np.linalg.svd(np.array(rows))
    normalised = vt[-1].reshape(3, 4)
    P = np.linalg.inv(Tp) @ normalised @ Tx
    P = P / P[2, 3] if abs(P[2, 3]) > 1e-12 else P / np.linalg.norm(P)
    return P, reprojection_rms(P, points3d, pixels)


def fit_plane_homography(plane_points, pixels):
    """3 x 3 homography from points on a plane (N x 2, in mm) to pixels, with at least 4 points. Returns (H, rms)."""
    plane_points = np.asarray(plane_points, dtype=float)
    pixels = np.asarray(pixels, dtype=float)
    if len(plane_points) < 4 or len(plane_points) != len(pixels):
        raise CalibrationError("at least 4 matching points are needed")
    X, Tx = _normalise(plane_points)
    x, Tp = _normalise(pixels)
    rows = []
    for (a, b, c), (u, v, w) in zip(X, x, strict=True):
        rows.append([a, b, c, 0, 0, 0, -u * a, -u * b, -u * c])
        rows.append([0, 0, 0, a, b, c, -v * a, -v * b, -v * c])
    _, _, vt = np.linalg.svd(np.array(rows))
    H = np.linalg.inv(Tp) @ vt[-1].reshape(3, 3) @ Tx
    H = H / H[2, 2]
    mapped = (H @ np.hstack([plane_points, np.ones((len(plane_points), 1))]).T).T
    rms = float(np.sqrt(np.mean(np.sum((mapped[:, :2] / mapped[:, 2:3] - pixels) ** 2, axis=1))))
    return H, rms


def triangulate(P1, P2, pixel1, pixel2):
    """Machine point seen by two cameras. Returns (point, residual_pixels), the residual being the mean reprojection error."""
    rows = []
    for P, (u, v) in ((P1, pixel1), (P2, pixel2)):
        rows.append(u * P[2] - P[0])
        rows.append(v * P[2] - P[1])
    _, _, vt = np.linalg.svd(np.array(rows))
    homogeneous = vt[-1]
    if abs(homogeneous[3]) < 1e-12:
        raise CalibrationError("the two rays are parallel")
    point = homogeneous[:3] / homogeneous[3]
    residual = float(np.mean([np.linalg.norm(project(P, point) - np.asarray(px)) for P, px in ((P1, pixel1), (P2, pixel2))]))
    return point, residual
