# Provisional CAD, version 0.2

Parametric CAD of the whole system (frame, axes, tool head, cameras, controls, optional wrist), written in Python with
[build123d](https://github.com/gumyr/build123d).

> **Provisional. Do not print yet.** Every dimension is an assumption, a typical catalogue value of a
> standard part, or a design decision of this version. **None is a measurement.** The design has only had a
> first-order hand calculation (`mech_review.py`), no finite-element analysis. Only the syringe barrel diameter comes from the manufacturer's catalogue.

## What is here

| File | Purpose |
|---|---|
| `params.py` | Every parameter, with its value and a source tag: `catalog`, `typical` (verify against the datasheet), `assumed` (measure it) or `decided`. |
| `parts.py` | The tool head and axis parts (version 0.1): 14 printed and 1 machined, plus dummies of the syringe and the actuator. |
| `system_parts.py` | Legacy parts of version 0.2 that no module owns yet (base plate maker, camera wedge, limit switch bracket and flag, control panel, quick-change knob) and the dummies (profiles, rails, motors, cameras). Do not add new parts here: make a module. |
| `system.py` | Collects every module into the world frame (two variants: fixed tool, or active wrist), holds the tool head, and runs the system checks: interferences at the corners of the travel, wrist swing, camera line of sight. |
| `layout.py` | Shared layout: constants, placement helpers and the `Pose` of the moving parts. No parts. |
| `modules/` | **One file per module.** Each owns its geometry and where it stands in the assembly (see below). |
| `build.py` | Builds every part, runs all the checks and exports STL files. |
| `render.py` | Renders overview sheets of the parts, the tool head and the whole system. |
| `mech_review.py` | First-order hand calculation of masses, moments, deflections, frequencies and the Z screw, with every assumption listed. |
| `wiring.py` | Provisional wiring map: cables, conductor counts, estimated lengths and the moving harness. Reads the pins from `firmware/board/controller_board/board_config.h` and checks them (`--check`, also in the CI); `--diagram` draws the block diagram. |
| `params_report.py` | Prints all parameters and their status as a Markdown table. |

## Modules

Every file in `modules/` that does not start with an underscore is a module, found automatically. A module may define:

| Name | What it is |
|---|---|
| `PARTS` | `{name: (maker, kind)}`: the parts to make (`printed` or `machined`) |
| `fixed(variant, setback)` | `{name: (shape, kind)}`: items that never move |
| `moving(pose)` | `{name: (shape, kind, group)}`: items that move with `x`, `y`, `z` or the `tool` (`pose` is a `layout.Pose`) |
| `ALLOWED` | pairs of items that overlap by design (a screw in its dummy motor) |

Rules, so that modules can be developed in parallel without stepping on each other:

- Adding or changing a module touches **only its own file**, never `system.py` or `build.py`.
- A name used by two modules, or by a module and a legacy catalogue, is an error (`ValueError`).
- Current modules: `frame`, `bracing`, `x_axis`, `z_stage`, `z_brake`, `wrist`, `wrist_drive`, `cameras`, `microscope`, `electronics`, `controls`, `work_area`, `specimen_fixture`, `cable_chain`, `tool_mount`.
- The refactor to modules does not change the result: the 30 parts, both assemblies and every check give the same numbers as before.

## Findings of the module cards (06/11/2026)

- **The build did not check the active wrist at the travel limits.** `build.py` now also sweeps the wrist variant at the corners of
  the travel and swings the wrist at the four corners and the centre, not only at x = y = 0. That found two real problems:
  the yoke arms (27 to 35 mm each side of the needle) touch the phantom block when the tip is below 23 mm, so the wrist variant
  has a **minimum tip height** (`WRIST_MIN_TIP`, 2 mm above the lowest one; the firmware has to keep to it and the bottom stop of Z
  has to sit there), and a tilt of -30 degrees near the front of the travel hit **camera A**. Camera A moved from 95 to 175 mm in
  front of the needle and from 135 to 170 mm high; its largest angle to the optical axis fell from 51 to 30 degrees.
- **Stiffening:** a second 2020 profile under the crossbeam, joined by printed plates, and two diagonal braces. With assumed joint
  stiffness the torsion of the crossbeam falls from about 270 to about 80 um at the tip and the sway mode rises from an unreliable
  upper bound to about 94 Hz (`mech_review.py`). The printed brackets that hold the braces are the weak point.
- **Wrist drive:** a worm and a split printed sector (anti-backlash) on the tilt axis, with a NEMA 11, as envelopes. The axis names
  now follow the firmware and the simulation: **B is the rotation about X** (what this CAD draws) and **A the rotation about Y**,
  the outer axis (card `mech-wrist-2`, below).
- **Wrist axis A (card `mech-wrist-2`):** the whole wrist turns about Y through the needle hub on a printed stage plate (`wrist_a_base`,
  bearing boss, 14 mm gap, which moves the work area 14 mm back). The sweep now covers A as well as B: **A = +-30 degrees is clean only
  with the tip at 38 mm or higher; at the lowest tips A is limited to +-5 degrees** (+-6.5 already touches the phantom with B = +30; the
  contact is the cradle). The firmware must keep to these limits like the minimum tip height. The drive of A is a concept, not
  geometry: a worm on a 110-tooth arc (about 489 steps per degree at 1/8 microstepping); its motor mount, which has to reach round the
  yoke plate, is the open part.
- **Microscope:** fixed, on the left, with a 100 mm working distance. Only the neighbourhood of the target is in its field, and the
  wrist yoke blocks the view when the tool is at the far left.
- **Specimen fixture:** generic V block and clamp posts, not placed by default. With the wrist the needle has to stay within a few
  millimetres of the centre line at low heights, because the yoke arms straddle the specimen.

## Parts

Printed (22): `hamilton_clamp`, `tool_backplate`, `plunger_motor_mount`, `plunger_coupler`, `angle_wedge_15`,
`angle_wedge_30`, `angle_wedge_45`, `z_carriage_plate`, `nut_bracket`, `motor_mount_nema17`,
`bearing_support_608`, `camera_plate`, `phantom_tray`, `tolerance_coupon` (the first thing to print: it
measures the printer), `camera_wedge_45`, `limit_switch_bracket`, `limit_flag`, `control_panel`, `z_knob`,
`quick_knob`, `wrist_cradle` and `wrist_yoke`. Machined in aluminium (3): `stage_plate`, `z_riser` and `base_plate`.

## Run

```
pip install -r requirements-cad.txt
python cad/build.py out
python cad/render.py out out/sheets
python cad/mech_review.py
```

`build.py` ends with `BUILD OK` only if every part is a single valid solid, every printed part fits the
assumed print volume, the tool head and the whole system have no interferences (at the corners of the
travel plus a 4 mm hard-stop margin, and over the +/-30 degree wrist swing), and both cameras see the needle
tip over a grid of 27 positions. It takes a few minutes. On Windows keep the virtual
environment on a short path: the 260-character limit breaks the installation of these libraries.

## To replace the assumptions

Measure the real value, change it in `params.py`, run `build.py` again, and change its source tag from
`assumed` or `typical` to a measurement. Run `python cad/params_report.py` for the list of what is still
unmeasured.

## Findings of version 0.2

- The riser must reach 160 mm: with 135 mm its leg hit the end of the Y plate at full travel.
- A camera straight above cannot see the needle tip (barrel and hub hide it): the first camera is oblique, at 40 degrees.
- The tip moves up to about 47 degrees (camera A) and 40 degrees (camera B) off the optical axis over the travel.
- An active wrist with the pivot at the hub plane needs the carriage plate at least 100 mm behind the needle axis for +/-30 degrees, and at +30 degrees the tip must be at 20 mm or higher or the cradle hits the phantom.
- First-order hand calculation: the crossbeam in torsion and the Z screw (marginal self-locking) are the weak points.

## Not designed yet

The nut linkage of each screw to its carriage and the screw supports (motors and screws are envelopes), the
Y and bottom-Z limit switches, the lever latch of the quick-change interface, the motor mount of the A drive,
the panel lid and wiring, the electronics enclosure, the bracing of the frame, cable management and a wash station.

The STL files are generated and not committed.

## Travel per axis

`params.py` has `TRAVEL_X`, `TRAVEL_Y` and `TRAVEL_Z` (100 mm each by default). A study sets them with the environment variable
`VERNIER_TRAVEL="x,y,z"` and everything that follows the travel (rails, plates, screws, uprights, base, crossbeam height, switches, the
sweeps of `system.py`, cable lengths) follows it. With the defaults the build is identical to before. With 200 x 200 x 100 mm the structure
is fine and every collision is a station that sat outside the reach of the gantry (tool rack, wash tray, control panel, microscope, camera
B): they have to be laid out again inside the travel (card mech-estaciones). `python cad/mech_review.py` prints the loads, the beam sag and
twist and the critical speed of each screw for the chosen travel; T8 screws are not enough above about 300 mm.

