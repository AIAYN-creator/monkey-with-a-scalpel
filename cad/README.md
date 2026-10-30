# Provisional CAD, version 0.1

Parametric CAD of the tool head and its supporting parts, written in Python with
[build123d](https://github.com/gumyr/build123d).

> **Provisional. Do not print yet.** Every dimension is an assumption, a typical catalogue value of a
> standard part, or a design decision of this version. **None is a measurement.** The design has not had a
> mechanical review. Only the syringe barrel diameter comes from the manufacturer's catalogue.

## What is here

| File | Purpose |
|---|---|
| `params.py` | Every parameter, with its value and a source tag: `catalog`, `typical` (verify against the datasheet), `assumed` (measure it) or `decided`. |
| `parts.py` | The parts: 14 printed and 1 machined, plus dummies of the syringe and the actuator for the assembly. |
| `build.py` | Builds every part, checks it and exports STL files. |
| `render.py` | Renders overview sheets of the parts and of the tool-head assembly. |
| `params_report.py` | Prints all parameters and their status as a Markdown table. |

## Parts

Printed: `hamilton_clamp`, `tool_backplate`, `plunger_motor_mount`, `plunger_coupler`, `angle_wedge_15`,
`angle_wedge_30`, `angle_wedge_45`, `z_carriage_plate`, `nut_bracket`, `motor_mount_nema17`,
`bearing_support_608`, `camera_plate`, `phantom_tray` and `tolerance_coupon` (the first thing to print: it
measures the printer). Machined in aluminium: `stage_plate`.

## Run

```
pip install -r requirements-cad.txt
python cad/build.py out
python cad/render.py out out/sheets
```

`build.py` ends with `BUILD OK` only if every part is a single valid solid, every printed part fits the
assumed print volume, and the tool-head assembly has no interferences. On Windows keep the virtual
environment on a short path: the 260-character limit breaks the installation of these libraries.

## To replace the assumptions

Measure the real value, change it in `params.py`, run `build.py` again, and change its source tag from
`assumed` or `typical` to a measurement. Run `python cad/params_report.py` for the list of what is still
unmeasured.

## Not designed yet

The frame, an active wrist, the latch of the quick-change interface, the manual knob of the Z axis, the
mounts of limit switches, abort button and emergency stop, camera arms, a wash station, cable management
and the electronics enclosure.

The STL files are generated and not committed.
