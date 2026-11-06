# Host software

Software that runs on the PC next to the controller: coordinates and calibration today; the control layer, the camera-overlay
viewer and the LLM interface are planned (cards `sw-host`, `sw-overlay`, `sw-llm`). Nothing here has run on hardware.

## `link/` (card `sw-host`)

The PC side of the serial protocol of the controller.

- **`protocol.py`**: parses the replies (`ok ...` or `error:<code>`), the STATUS fields, and builds MOVE lines.
- **`transport.py`**: `SerialTransport` for a real port (needs `pyserial`, not tested without hardware) and `SimTransport`, which
  runs the **real controller core on a simulated plant** (`firmware/sim/sim_main.cpp`, built with g++). Time in the simulation only
  passes when the host asks for it, so tests are deterministic. It can press the ABORT button, cut the motor power and make an axis
  slip, as after lost steps.
- **`session.py`**: typed commands, a rejected command raises `CommandRejected` with the error code, every exchange goes to a log,
  and the **heartbeat**: the controller aborts after 1000 ms of silence, so `start_heartbeat` pings from a thread on a real port and
  `run_for` does it in simulated time. `silent_for` leaves the controller alone to test the watchdog.
- **`chainlog.py`**: a log of JSON lines where each entry carries the hash of the one before, so an edited, deleted or reordered
  entry is detected by `verify`. It protects against accidents and casual edits, not against someone who rewrites the whole file.
- **`test_link.py`**: protocol parsing, the log (clean, reopened, edited, deleted, swapped, garbage), and a session against the
  simulated controller: homing, moves, rejected moves, STOP, the watchdog abort, the ABORT button, the ABORT command, a limit fault
  from lost steps, motor power loss and CLEAR. Run `python host/link/test_link.py`; it is part of the CI.

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
