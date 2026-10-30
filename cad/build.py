"""Build every part, check it, check the tool-head assembly for interferences and export the STL files.

Usage, from the repository root (needs build123d, see requirements-cad.txt):
    python cad/build.py OUT_DIR

Exit code 0 only if every check passes. The STL files are generated, not committed.
"""
import itertools
import json
import sys
from pathlib import Path

import params as P
import parts
from build123d import Pos, export_stl

PETG_DENSITY = 1.27  # g/cm3, typical


def sorted_dims(shape):
    bb = shape.bounding_box()
    return sorted((bb.size.X, bb.size.Y, bb.size.Z))


def fits(shape, volume=P.PRINT_VOLUME):
    return all(a <= b for a, b in zip(sorted_dims(shape), sorted(volume), strict=True))


def overlap(a, b):
    try:
        shared = a & b
        return float(shared.volume) if shared is not None else 0.0
    except Exception:  # noqa: BLE001 - an empty intersection may raise depending on the version
        return 0.0


def tool_head():
    """The tool head with its dummies, in the tool coordinates, with the plunger at mid-stroke."""
    mid_out = P.PLUNGER_OUT + P.STROKE / 2
    barrel, plunger, needle = parts.dummy_syringe(mid_out)
    body, shaft = parts.dummy_actuator()
    button_mid = P.BARREL_LENGTH + mid_out + P.BUTTON_T / 2
    return {
        "hamilton_clamp": Pos(0, 0, P.CLAMP_Z) * parts.hamilton_clamp(),
        "tool_backplate": parts.tool_backplate(),
        "plunger_motor_mount": parts.plunger_motor_mount(),
        "plunger_coupler": Pos(0, 0, button_mid) * parts.plunger_coupler(),
        "syringe_barrel": barrel,
        "syringe_plunger": plunger,
        "syringe_needle": needle,
        "actuator_body": body,
        "actuator_shaft": shaft,
    }


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    problems = []
    report = []
    for name, make in {**parts.PRINTED, **parts.MACHINED}.items():
        shape = make()
        solids = len(shape.solids())
        valid = bool(shape.is_valid)
        dims = sorted_dims(shape)
        ok = solids == 1 and valid and shape.volume > 0
        printable = name in parts.MACHINED or fits(shape)
        if not ok:
            problems.append(f"{name}: solids={solids} valid={valid}")
        if not printable:
            problems.append(f"{name}: {dims} does not fit the print volume {P.PRINT_VOLUME}")
        report.append({
            "part": name,
            "kind": "machined" if name in parts.MACHINED else "printed",
            "size_mm": [round(d, 1) for d in dims],
            "volume_cm3": round(shape.volume / 1000, 2),
            "mass_g_solid_petg": round(shape.volume / 1000 * PETG_DENSITY, 1),
            "ok": ok and printable,
        })
        export_stl(shape, str(out / f"{name}.stl"))

    head = tool_head()
    for name, shape in head.items():
        export_stl(shape, str(out / f"head_{name}.stl"))
    skip = {frozenset(("actuator_body", "actuator_shaft"))}  # the shaft belongs to the actuator
    interferences = {}
    for a, b in itertools.combinations(head, 2):
        if frozenset((a, b)) in skip:
            continue
        shared = overlap(head[a], head[b])
        if shared > 0.5:
            interferences[f"{a} / {b}"] = round(shared, 2)
            problems.append(f"interference {a} / {b}: {shared:.2f} mm3")

    (out / "report.json").write_text(json.dumps({"parts": report, "interferences": interferences}, indent=1))
    for row in report:
        print(f"{row['part']:22s} {row['kind']:9s} {row['size_mm']}  {row['volume_cm3']:6.2f} cm3  ok={row['ok']}")
    print("tool head interferences:", interferences or "none")
    print("BUILD OK" if not problems else "BUILD FAILED: " + "; ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "cad_out"))
