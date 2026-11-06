# Host software

Software that runs on the PC next to the controller: the link, coordinates and calibration, simulated tool models, the camera-overlay
viewer and the LLM interface (cards `sw-host`, `sw-coords`, `sw-overlay`, `sw-llm`, and the tool cards). Nothing here has run on hardware.

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

## `toolsim/` (cards `t-inject`, `t-probe`, `t-scalpel`, `t-drill`, `t-fluid`, `t-grip`, `t-cautery`, `t-sense`, `stn-wash`)

Behaviour models of the eight tools and of the wash station. Each is built from its descriptor (`tools/<name>/descriptor.yaml`) and enforces
the `limits` written there, so the limit lives in one place. A model refuses what it must refuse (a cut deeper than the stop, a dose over
the limit, a cautery pulse over its energy budget, a reading without a dark reference), needs `TOOL ON`, and after an abort is in the
safe state the descriptor declares (the drill and the cautery lose power at once; the gripper keeps holding). `wash.py` simulates the
cleaning sequence with a carry-over model. These are models of behaviour for the software and the tests, not physics, and every number is
provisional. `python host/toolsim/test_toolsim.py` (part of the CI).

## `overlay/` (card `sw-overlay`)

The viewer over the two cameras and the microscope: tip, target, error in mm, firmware state, tool, approval and the anatomical coordinates
of the tip in the sample frame. Each element comes with a sentence that says how its number was computed (`explain`). Output is SVG (the frame
embedded as a PNG, live text and vector shapes on top), so it needs only numpy. The only source built is `SimSource`, which draws synthetic
frames from pinhole projection matrices; a video or live camera needs a source that decodes the images and a tip detector (cards `p1-10`
and `p1-12`). Colour: amber means look here, red only a stop or a fault. `python host/overlay/test_overlay.py` (part of the CI).

## `llm/` (card `sw-llm`)

The interface between a language model and the machine. The model never sends a command: it proposes steps that name a capability from a
closed list (the machine's and every tool's, built from the descriptors), with typed parameters. A deterministic validator (no AI) checks
the plan statically and by dry-running it on a simulated world with the same code that will run it; a person approves the exact plan
(the approval carries its hash, so any edit voids it); the plan is narrated step by step from templates; every event goes to a hash-chained
log; a stop or a fault aborts. The model is replaceable by a script (`ScriptedLLM`), which is how the tests and simulations run. A client
for a real model is not written: it only has to implement `propose(goal, description, feedback)`. `python host/llm/test_llm.py` (part of the CI).

## Calibration procedure (proposal, to test with the real cameras)

1. Place a printed target with known points at several heights and positions, and move the tool tip to each point with the
   gantry, so the machine coordinates are known from the controller.
2. Detect the target or the tip in each camera and fit `fit_projection` per camera. Keep the reprojection error: it is the
   floor of what the cameras can tell.
3. Triangulate the tip with both cameras and compare it with the controller position. The difference is the calibration error
   that `simulation/sweep_errores.py` called the hard floor of the loop.
4. Repeat after any movement of a camera. The microscope is calibrated the same way over its own, smaller field.
