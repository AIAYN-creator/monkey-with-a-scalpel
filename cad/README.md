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
| `system_parts.py` | The parts added in version 0.2 (frame riser, base plate, camera wedge, limit switch bracket and flag, control panel, Z knob, quick-change knob, active wrist) and the dummies (profiles, rails, motors, cameras). |
| `system.py` | Places everything in world coordinates (two variants: fixed tool, or active wrist) and runs the system checks: interferences at the corners of the travel, wrist swing, camera line of sight. |
| `build.py` | Builds every part, runs all the checks and exports STL files. |
| `render.py` | Renders overview sheets of the parts, the tool head and the whole system. |
| `mech_review.py` | First-order hand calculation of masses, moments, deflections, frequencies and the Z screw, with every assumption listed. |
| `wiring.py` | Provisional wiring map: cables, conductor counts, estimated lengths and the moving harness. Reads the pins from `firmware/board/controller_board/board_config.h` and checks them (`--check`, also in the CI); `--diagram` draws the block diagram. |
| `params_report.py` | Prints all parameters and their status as a Markdown table. |

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
Y and bottom-Z limit switches, the lever latch of the quick-change interface, the wrist drive and its B axis,
the panel lid and wiring, the electronics enclosure, the bracing of the frame, cable management and a wash station.

The STL files are generated and not committed.
