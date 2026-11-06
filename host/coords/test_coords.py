"""Self-checks of the coordinate frames and the camera calibration. Usage, from the repository root:

    python host/coords/test_coords.py

Every check compares against a value computed by hand or a known synthetic truth. Exit code 1 on a failure.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coords import (
    CalibrationError,
    FrameError,
    SampleFrame,
    check_spacing,
    fit_plane_homography,
    fit_projection,
    project,
    reprojection_rms,
    triangulate,
)

FAILURES = []


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


def rotation_z(degrees):
    c, s = np.cos(np.radians(degrees)), np.sin(np.radians(degrees))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def test_frame_by_hand():
    print("frame: values computed by hand")
    # origin at (10, 20, 5); the second landmark 7 mm behind it, i.e. towards -Y?  Anterior is -Y here (towards the user is +Y).
    origin = np.array([10.0, 20.0, 5.0])
    rear = np.array([10.0, 27.0, 5.0])  # behind the origin: further from the front, which is -Y
    frame = SampleFrame.from_landmarks(origin, rear)
    check(np.allclose(frame.to_sample(origin), [0, 0, 0]), "the origin maps to (0, 0, 0)")
    check(np.allclose(frame.to_sample(rear), [-7.0, 0.0, 0.0]), "the rear landmark is 7 mm behind: AP = -7")
    right_point = origin + np.array([3.0, 0.0, 0.0])  # +X in the machine
    ap, ml, dv = frame.to_sample(right_point)
    check(abs(ap) < 1e-9 and abs(dv) < 1e-9, "a point to the side has AP = 0 and DV = 0")
    # anterior = -Y, up = +Z, right = anterior x up = (-Y) x Z = -X, so +X is to the sample's left
    check(abs(ml + 3.0) < 1e-9, "with the front towards -Y, +X is the left of the sample: ML = -3")
    check(abs(frame.to_sample(origin + np.array([0, 0, 4.0]))[2] - 4.0) < 1e-9, "4 mm up is DV = +4")
    depth_frame = SampleFrame.from_landmarks(origin, rear, ventral_positive=True)
    check(abs(depth_frame.to_sample(origin + np.array([0, 0, -2.0]))[2] - 2.0) < 1e-9, "2 mm down is depth +2")


def test_frame_round_trip_and_orthonormal():
    print("frame: round trip and orthonormality")
    rng = np.random.default_rng(1)
    for _ in range(50):
        origin = rng.uniform(-50, 50, 3)
        rear = origin + rotation_z(rng.uniform(0, 360)) @ np.array([rng.uniform(3, 10), 0, rng.uniform(-1, 1)])
        frame = SampleFrame.from_landmarks(origin, rear, level=bool(rng.integers(0, 2)))
        check(np.allclose(frame.rotation.T @ frame.rotation, np.eye(3), atol=1e-12), "axes are orthonormal")
        check(abs(np.linalg.det(frame.rotation) - 1.0) < 1e-12, "the frame is right-handed")
        point = rng.uniform(-60, 60, 3)
        check(np.allclose(frame.to_machine(*frame.to_sample(point)), point, atol=1e-9), "round trip machine, sample, machine")


def test_tilt_and_level():
    print("frame: tilt of the landmark line")
    origin = np.array([0.0, 0.0, 10.0])
    rear = np.array([0.0, 10.0, 10.0 - 1.0])  # the rear landmark is 1 mm lower: the sample is tilted nose up by atan(1/10)
    levelled = SampleFrame.from_landmarks(origin, rear, level=True)
    follow = SampleFrame.from_landmarks(origin, rear, level=False)
    check(abs(levelled.pitch_deg - np.degrees(np.arctan2(1.0, 10.0))) < 1e-9, "the pitch is reported (about 5.71 degrees)")
    check(abs(levelled.to_sample(rear)[2] + 1.0) < 1e-9, "levelled frame: the rear landmark is 1 mm below (DV = -1)")
    check(abs(follow.to_sample(rear)[2]) < 1e-9, "frame following the line: the rear landmark has DV = 0")
    check(abs(follow.to_sample(rear)[0] + np.hypot(10.0, 1.0)) < 1e-9, "and its AP is minus the true distance")


def test_frame_errors():
    print("frame: degenerate landmarks")
    for name, args in (
        ("coincident landmarks", ((1, 2, 3), (1, 2, 3))),
        ("landmark line parallel to up", ((0, 0, 5), (0, 0, 0))),
    ):
        try:
            SampleFrame.from_landmarks(*args, level=False)
            check(False, f"{name} must raise FrameError")
        except FrameError:
            pass
    try:
        SampleFrame.from_landmarks((0, 0, 5), (0, 0, 0), level=True)
        check(False, "a vertical line cannot be levelled: FrameError")
    except FrameError:
        pass


def test_spacing_prior():
    print("frame: a reference spacing is a prior")
    check(check_spacing(4.1, 4.0, 0.3)["agrees"], "4.1 against 4.0 with 0.3 tolerance agrees")
    result = check_spacing(5.0, 4.0, 0.3)
    check(not result["agrees"] and abs(result["difference_mm"] - 1.0) < 1e-9, "5.0 against 4.0 does not agree and says by how much")


def synthetic_camera(rng, centre, target, focal=1200.0, size=(1920, 1080)):
    """A pinhole camera at `centre` looking at `target`, with the principal point at the image centre."""
    z = np.asarray(target, float) - np.asarray(centre, float)
    z /= np.linalg.norm(z)
    x = np.cross(z, [0, 0, 1.0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.vstack([x, y, z])
    K = np.array([[focal, 0, size[0] / 2], [0, focal, size[1] / 2], [0, 0, 1.0]])
    return K @ np.hstack([R, (-R @ np.asarray(centre, float)).reshape(3, 1)])


def test_projection_fit():
    print("camera: projection fitted from correspondences")
    rng = np.random.default_rng(2)
    truth = synthetic_camera(rng, (300.0, -250.0, 220.0), (0.0, 0.0, 30.0))
    points = np.column_stack([rng.uniform(-40, 40, 30), rng.uniform(-40, 40, 30), rng.uniform(0, 60, 30)])
    pixels = project(truth, points)
    P, rms = fit_projection(points, pixels)
    check(rms < 1e-6, f"noise-free fit reprojects below 1e-6 px (got {rms:.2e})")
    probe = np.array([[5.0, -7.0, 20.0]])
    check(np.linalg.norm(project(P, probe) - project(truth, probe)) < 1e-5, "the fit predicts a point it was not given")
    noisy = pixels + rng.normal(0, 0.5, pixels.shape)
    _, rms_noisy = fit_projection(points, noisy)
    check(0.2 < rms_noisy < 0.8, f"with 0.5 px of noise the residual is about 0.5 px (got {rms_noisy:.2f})")
    check(abs(reprojection_rms(truth, points, pixels)) < 1e-6, "reprojection_rms of the truth is zero")


def test_projection_errors():
    print("camera: degenerate calibration data")
    rng = np.random.default_rng(3)
    flat = np.column_stack([rng.uniform(-40, 40, 12), rng.uniform(-40, 40, 12), np.zeros(12)])
    for name, call in (
        ("coplanar points", lambda: fit_projection(flat, rng.uniform(0, 100, (12, 2)))),
        ("too few points", lambda: fit_projection(flat[:4], rng.uniform(0, 100, (4, 2)))),
    ):
        try:
            call()
            check(False, f"{name} must raise CalibrationError")
        except CalibrationError:
            pass


def test_triangulation():
    print("camera: two cameras give the 3D position")
    rng = np.random.default_rng(4)
    cam_a = synthetic_camera(rng, (0.0, 260.0, 160.0), (0.0, 0.0, 30.0))
    cam_b = synthetic_camera(rng, (170.0, 0.0, 45.0), (0.0, 0.0, 30.0))
    errors = []
    for _ in range(200):
        point = np.array([rng.uniform(-45, 45), rng.uniform(-45, 45), rng.uniform(15, 115)])
        px_a = project(cam_a, point) + rng.normal(0, 0.3, 2)
        px_b = project(cam_b, point) + rng.normal(0, 0.3, 2)
        found, residual = triangulate(cam_a, cam_b, px_a, px_b)
        errors.append(np.linalg.norm(found - point))
        check(residual < 2.0, "the reprojection residual stays small")
    check(np.mean(errors) < 0.1, f"mean 3D error below 0.1 mm with 0.3 px of noise (got {np.mean(errors):.3f} mm)")
    exact, _ = triangulate(cam_a, cam_b, project(cam_a, [1.0, 2.0, 3.0]), project(cam_b, [1.0, 2.0, 3.0]))
    check(np.allclose(exact, [1.0, 2.0, 3.0], atol=1e-8), "noise-free triangulation is exact")


def test_homography():
    print("camera: homography of a plane")
    H_true = np.array([[12.0, 1.5, 900.0], [-0.8, 11.0, 500.0], [1e-4, 2e-4, 1.0]])
    rng = np.random.default_rng(5)
    plane = rng.uniform(-40, 40, (16, 2))
    mapped = (H_true @ np.hstack([plane, np.ones((16, 1))]).T).T
    pixels = mapped[:, :2] / mapped[:, 2:3]
    H, rms = fit_plane_homography(plane, pixels)
    check(rms < 1e-6, f"noise-free homography reprojects below 1e-6 px (got {rms:.2e})")
    check(np.allclose(H, H_true / H_true[2, 2], rtol=1e-6, atol=1e-6), "the homography is recovered")


def main():
    for test in (test_frame_by_hand, test_frame_round_trip_and_orthonormal, test_tilt_and_level, test_frame_errors,
                 test_spacing_prior, test_projection_fit, test_projection_errors, test_triangulation, test_homography):
        test()
    print("COORDS OK" if not FAILURES else f"COORDS FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
