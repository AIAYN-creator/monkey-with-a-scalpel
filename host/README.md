# Host software

Software that runs on the PC next to the controller: coordinates and calibration today; the control layer, the camera-overlay
viewer and the LLM interface are planned (cards `sw-host`, `sw-overlay`, `sw-llm`). Nothing here has run on hardware.

## `coords/` (card `sw-coords`)

- **`frames.py`**: a sample frame defined by two landmarks (`SampleFrame.from_landmarks`). The machine frame is the one of
  `cad/system.py` (X right, Y towards the user, Z up, in mm). The sample frame has AP towards the front of the sample, ML
  towards its right and DV towards its top; `ventral_positive=True` reports depth. The first landmark is the origin and the
  second lies behind it. `level=True` assumes the sample is levelled and only reports the tilt of the landmark line.
  `check_spacing` compares a measured landmark spacing with a reference value, because a table value is a prior, not a
  measurement.
- **`camera.py`**: a pinhole camera as a 3 x 4 matrix fitted from correspondences (`fit_projection`, direct linear transform
  with normalisation, at least 6 non-coplanar points), a plane homography (`fit_plane_homography`) and two-camera
  triangulation (`triangulate`). Lens distortion is not modelled: undistort the images first.
- **`test_coords.py`**: self-checks against values computed by hand and synthetic truths (round trip, orthonormality, tilt,
  degenerate landmarks, noise-free and noisy calibration, triangulation error below 0.1 mm with 0.3 px of noise). Run
  `python host/coords/test_coords.py`; it is part of the CI.

## Calibration procedure (proposal, to test with the real cameras)

1. Place a printed target with known points at several heights and positions, and move the tool tip to each point with the
   gantry, so the machine coordinates are known from the controller.
2. Detect the target or the tip in each camera and fit `fit_projection` per camera. Keep the reprojection error: it is the
   floor of what the cameras can tell.
3. Triangulate the tip with both cameras and compare it with the controller position. The difference is the calibration error
   that `simulation/sweep_errores.py` called the hard floor of the loop.
4. Repeat after any movement of a camera. The microscope is calibrated the same way over its own, smaller field.
