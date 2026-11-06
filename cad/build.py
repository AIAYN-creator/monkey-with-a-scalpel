"""Build every part, check it, check the assemblies and export the STL files.

Usage, from the repository root (needs build123d, see requirements-cad.txt):
    python cad/build.py OUT_DIR

Checks: every part is one valid solid and the printed ones fit the print volume; the tool head has no
interferences; the whole system has none at the corners of the travel (with the hard-stop margin) and in
the wrist swing; both cameras see the needle tip over the whole travel. Exit code 0 only if all pass.
The STL files are generated, not committed.
"""
import json
import sys
from pathlib import Path

import modules
import params as P
import parts
import system as SYS
import system_parts as SP
from build123d import export_stl
from modules import wrist as WRIST

PETG_DENSITY = 1.27  # g/cm3, typical
WRIST_SETBACK = 110.0  # mm, from the swing search: 100 is the smallest that clears at 30 degrees
TILT_RENDER = 25.0


def sorted_dims(shape):
    bb = shape.bounding_box()
    return sorted((bb.size.X, bb.size.Y, bb.size.Z))


def fits(shape, volume=P.PRINT_VOLUME):
    return all(a <= b for a, b in zip(sorted_dims(shape), sorted(volume), strict=True))


def part_catalogue():
    """{name: (maker, kind)} of every part to make."""
    cat = {}
    for name, make in parts.PRINTED.items():
        cat[name] = (make, "printed")
    for name, make in SP.PRINTED_V2.items():
        cat[name] = (make, "printed")
    for name, make in parts.MACHINED.items():
        cat[name] = (make, "machined")
    for name, make in SP.MACHINED_V2.items():
        cat[name] = (make, "machined")
    for name, entry in modules.catalogue().items():
        if name in cat:
            raise ValueError(f"part {name!r} is in a legacy catalogue and in a module")
        cat[name] = entry
    cat["wrist_yoke"] = (lambda: WRIST.wrist_yoke(WRIST_SETBACK), "printed")
    return cat


def export_assembly(out, tag, fixed, moving):
    names = []
    for name, (shape, kind, *_rest) in {**{k: (v[0], v[1]) for k, v in fixed.items()}, **moving}.items():
        export_stl(shape, str(out / f"{tag}_{name}.stl"))
        names.append({"name": name, "kind": kind})
    return names


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    problems, report = [], []
    for name, (make, kind) in part_catalogue().items():
        shape = make()
        solids, valid, dims = len(shape.solids()), bool(shape.is_valid), sorted_dims(shape)
        ok = solids == 1 and valid and shape.volume > 0
        printable = kind == "machined" or fits(shape)
        if not ok:
            problems.append(f"{name}: solids={solids} valid={valid}")
        if not printable:
            problems.append(f"{name}: {dims} does not fit the print volume {P.PRINT_VOLUME}")
        report.append({
            "part": name,
            "kind": kind,
            "size_mm": [round(d, 1) for d in dims],
            "volume_cm3": round(shape.volume / 1000, 2),
            "mass_g_solid_petg": round(shape.volume / 1000 * PETG_DENSITY, 1),
            "ok": ok and printable,
        })
        export_stl(shape, str(out / f"{name}.stl"))

    # the tool head on its own (as in version 0.1)
    head = SYS.tool_head()
    for name, shape in head.items():
        export_stl(shape, str(out / f"head_{name}.stl"))
    head_items = {k: v for k, v in head.items()}
    head_inter = SYS.interferences(head_items)
    for k, v in head_inter.items():
        problems.append(f"tool head interference {k}: {v} mm3")

    system = {}
    # system, tool bolted to the Z carriage plate
    fixed = SYS.build_fixed("fixed")
    moving = SYS.build_moving("fixed")
    items = {k: v[0] for k, v in {**fixed, **moving}.items()}
    system["fixed_pose_mid"] = SYS.interferences(items)
    system["fixed_travel_corners"] = SYS.sweep_travel("fixed")
    export_assembly(out, "sysfixed", fixed, moving)
    # system with the active wrist, level and tilted
    fixed_w = SYS.build_fixed("wrist", WRIST_SETBACK)
    moving_w = SYS.build_moving("wrist", setback=WRIST_SETBACK)
    system["wrist_pose_mid"] = SYS.interferences({k: v[0] for k, v in {**fixed_w, **moving_w}.items()})
    system["wrist_swing"] = SYS.sweep_wrist_all(WRIST_SETBACK)
    export_assembly(out, "syswrist", fixed_w, moving_w)
    tilted = SYS.build_moving("wrist", zc=SYS.CARRIAGE_Z_MIN + 2 * P.TRAVEL / 3, theta=TILT_RENDER, setback=WRIST_SETBACK)
    export_assembly(out, "syswristtilt", fixed_w, tilted)
    for key, found in system.items():
        for k, v in found.items():
            problems.append(f"system {key}: {k} {v} mm3")

    # cameras: line of sight of the needle tip over a grid of the travel
    sight = {}
    for variant, setback in (("fixed", WRIST_SETBACK), ("wrist", WRIST_SETBACK)):
        sight[variant] = SYS.line_of_sight(variant, setback)
        for cam, res in sight[variant].items():
            if res["blocked"]:
                problems.append(f"line of sight {variant} camera {cam}: {len(res['blocked'])} of {res['total']} blocked")

    bom = {}
    for fx in (fixed, fixed_w):
        for name, (_shape, kind) in fx.items():
            bom.setdefault(kind, set()).add(name)
    (out / "report.json").write_text(json.dumps({
        "parts": report,
        "interferences": {"tool_head": head_inter, **system},
        "line_of_sight": sight,
        "wrist_setback_mm": WRIST_SETBACK,
        "travel_mm": P.TRAVEL,
        "tip_range_z_mm": [P.TIP_MIN, P.TIP_MIN + P.TRAVEL],
        "work_y_mm": {"fixed": SYS.work_y("fixed", WRIST_SETBACK), "wrist": SYS.work_y("wrist", WRIST_SETBACK)},
    }, indent=1))
    for row in report:
        print(f"{row['part']:22s} {row['kind']:9s} {row['size_mm']}  {row['volume_cm3']:6.2f} cm3  ok={row['ok']}")
    print("tool head interferences:", head_inter or "none")
    for key, found in system.items():
        print(f"system {key}:", found or "none")
    for variant, cams in sight.items():
        for cam, res in cams.items():
            print(f"line of sight, {variant}, camera {cam}: {len(res['blocked'])} of {res['total']} blocked, "
                  f"max {res['off_axis_deg']} deg off the optical axis")
    print("BUILD OK" if not problems else "BUILD FAILED: " + "; ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "cad_out"))
