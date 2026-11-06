"""Checks of the tool modules (cards t-inject, t-probe, t-scalpel, t-drill, t-fluid, t-grip, t-cautery, t-sense). Usage, from the repo root:

    python cad/tool_check.py

For every module that defines `TOOL` (see cad/modules/_toolkit.py) it builds the tool in the tool frame with the backplate and checks:
each printed part is one valid solid that fits the printer, there are no unplanned overlaps, the working point is where the descriptor
says, the whole tool fits inside the envelope of the injector head (so the geometric sweeps of build.py, which use the injector head,
also cover it), the mass is under the descriptor's, and the descriptor exists. Needs build123d. Exit code 1 on a failure.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))

import gen_tool_table as gen
import modules
import params as P
import parts
import system as SYS

FAILURES = []
PETG_G_PER_MM3 = 1.27e-3
EFFECTIVE = 0.4  # shells and infill of a printed part: 40 % of the solid


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


def bbox(shape):
    b = shape.bounding_box()
    return (b.min.X, b.max.X, b.min.Y, b.max.Y, b.min.Z, b.max.Z)


def union_bbox(shapes):
    boxes = [bbox(s) for s in shapes]
    return tuple(min(b[i] for b in boxes) if i % 2 == 0 else max(b[i] for b in boxes) for i in range(6))


def tool_modules():
    return [m for m in modules.discover() if hasattr(m, "TOOL")]


def main():
    backplate = parts.tool_backplate()
    envelope = union_bbox([backplate] + list(SYS.tool_head().values()))
    print("envelope of the injector head: x {:.0f}..{:.0f}  y {:.0f}..{:.0f}  z {:.0f}..{:.0f}".format(*envelope))
    descriptors = {d["name"]: d for d in gen.load_all()}
    found = tool_modules()
    names = sorted(m.TOOL["name"] for m in found)
    check(names == sorted(descriptors), f"a module for each descriptor: modules {names}, descriptors {sorted(descriptors)}")
    print(f"{'tool':9} {'parts':>5} {'mass g':>7} {'limit g':>7}  tip z")
    for module in found:
        spec = module.TOOL
        name = spec["name"]
        items = dict(module.assembly())
        d = descriptors.get(name)
        check(d is not None, f"{name}: has a descriptor")
        shapes = {k: v[0] for k, v in items.items()}
        kinds = {k: v[1] for k, v in items.items()}
        for key, shape in shapes.items():
            if kinds[key] == "printed":
                check(len(shape.solids()) == 1 and bool(shape.is_valid) and shape.volume > 0, f"{name}: {key} is one valid solid")
                dims = sorted(bbox(shape)[i + 1] - bbox(shape)[i] for i in (0, 2, 4))
                check(all(a <= b for a, b in zip(dims, sorted(P.PRINT_VOLUME))), f"{name}: {key} fits the printer ({dims})")
        allowed = getattr(module, "TOOL_ALLOWED", set())
        everything = dict(shapes)
        everything["tool_backplate"] = backplate
        names_all = list(everything)
        clashes = {}
        for i, a in enumerate(names_all):
            for b in names_all[i + 1:]:
                if frozenset((a, b)) in allowed:
                    continue
                v = SYS.overlap(everything[a], everything[b])
                if v > 0.5:
                    clashes[f"{a} / {b}"] = round(v, 1)
        check(not clashes, f"{name}: no unplanned overlaps {clashes}")
        box = union_bbox(list(shapes.values()))
        if name != "injector":
            check(all(box[i] >= envelope[i] - 0.5 if i % 2 == 0 else box[i] <= envelope[i] + 0.5 for i in range(6)),
                  f"{name}: inside the injector envelope ({', '.join(f'{v:.1f}' for v in box)})")
        tip_item = spec.get("tip_item")
        if tip_item is None:
            tip_item = {"scalpel": "scalpel_blade", "probe": "probe_stylus", "drill": "drill_bit", "fluid": "fluid_nozzle_a",
                        "cautery": "cautery_electrode", "sensor": "sensor_fibre"}.get(name)
        tip_z = bbox(shapes[tip_item])[4] if tip_item else min(bbox(shapes[k])[4] for k in shapes if k.startswith("gripper_jaw"))
        check(abs(tip_z - spec["tip_z"]) < 0.5, f"{name}: the working point is at z = {tip_z:.1f}, expected {spec['tip_z']}")
        if d is not None:
            check(abs(d["tip_mm"][2] - spec["tip_z"]) < 0.5, f"{name}: the descriptor tip_mm z is {d['tip_mm'][2]}, the module says {spec['tip_z']}")
        printed = sum(shapes[k].volume for k in shapes if kinds[k] == "printed") * PETG_G_PER_MM3 * EFFECTIVE
        mass = printed + sum(spec["dummy_mass_g"].values())
        limit = d["mass_g"] if d else 0
        dummies = {k for k in shapes if kinds[k] == "dummy"}
        check(dummies <= set(spec["dummy_mass_g"]), f"{name}: a mass for every dummy ({sorted(dummies - set(spec['dummy_mass_g']))})")
        check(mass <= limit, f"{name}: mass {mass:.0f} g is above the descriptor's {limit} g")
        print(f"{name:9} {len(shapes):5d} {mass:7.0f} {limit:7.0f}  {tip_z:6.1f}")
    print("TOOLS OK" if not FAILURES else f"TOOLS FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
