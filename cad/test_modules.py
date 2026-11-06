"""Tests of the CAD module registry and of the assembly it produces (needs build123d). Usage, from the repository root:

    python cad/test_modules.py

Checks the rules that keep parallel work safe: no name defined twice, every ALLOWED pair names real items, every part of a
module builds one valid solid, the assembly names are the same in every pose, and a module added or clashing is detected.
Exit code 1 on a failure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import modules
import system as SYS
from layout import Pose

FAILURES = []


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


def test_discovery():
    print("discovery")
    found = [m.__name__.rsplit(".", 1)[-1] for m in modules.discover()]
    check(found == sorted(found), "modules are discovered in alphabetical order")
    check(len(found) >= 10, f"at least 10 modules are found (got {len(found)})")
    check(all(not name.startswith("_") for name in found), "no private module is loaded")


def test_unique_names():
    print("unique names")
    catalogue = modules.catalogue()
    check(len(catalogue) > 20, f"the catalogue has parts ({len(catalogue)})")
    for variant in ("fixed", "wrist"):
        fixed = modules.fixed(variant, 110.0)
        moving = modules.moving(Pose(variant=variant))
        check(not (set(fixed) & set(moving)), f"{variant}: no item is both fixed and moving")
    names_fixed = set(modules.fixed("fixed", 110.0))
    names_wrist = set(modules.fixed("wrist", 110.0))
    check(names_fixed == names_wrist, "the fixed items are the same in both variants")
    for pose in (Pose(), Pose(xc=-50, yc=50, zc=SYS.CARRIAGE_Z_MAX), Pose(variant="wrist", theta=-30), Pose(variant="wrist", xc=50)):
        names = set(modules.moving(pose))
        base = set(modules.moving(Pose(variant=pose.variant)))
        check(names == base, f"the moving items do not depend on the position ({pose.variant}, x={pose.xc}, theta={pose.theta})")


def test_allowed_pairs_are_real():
    print("allowed pairs name real items")
    everything = set(SYS.build_fixed("wrist", 110.0)) | set(SYS.build_moving("wrist", setback=110.0)) | set(SYS.tool_head())
    everything |= set(SYS.build_fixed("fixed", 110.0)) | set(SYS.build_moving("fixed"))
    for pair in sorted(SYS.ALLOWED, key=sorted):
        for name in pair:
            check(name in everything, f"the allowed pair {sorted(pair)} names {name}, which is not in any assembly")


def test_parts_are_valid():
    print("every part of every module is one valid solid")
    for name, (make, kind) in modules.catalogue().items():
        shape = make()
        check(len(shape.solids()) == 1 and bool(shape.is_valid) and shape.volume > 0, f"{name} is one valid solid")
        check(kind in ("printed", "machined"), f"{name} has a known kind ({kind})")


def test_kinds_and_groups():
    print("kinds and groups")
    for variant in ("fixed", "wrist"):
        for name, (_shape, kind) in modules.fixed(variant, 110.0).items():
            check(kind in ("printed", "machined", "purchased", "dummy"), f"fixed item {name} has a known kind ({kind})")
        for name, (_shape, kind, group) in SYS.build_moving(variant, setback=110.0).items():
            check(kind in ("printed", "machined", "purchased", "dummy"), f"moving item {name} has a known kind ({kind})")
            check(group in ("x", "y", "z", "tool"), f"moving item {name} has a known group ({group})")


def test_clash_is_detected():
    print("a clash is an error")
    path = Path(modules.__file__).parent / "zz_clash_probe.py"
    try:
        path.write_text('from build123d import Box\n\nPARTS = {"base_plate": (lambda: Box(1, 1, 1), "printed")}\n', encoding="utf-8")
        raised = False
        try:
            modules.catalogue()
        except ValueError:
            raised = True
        check(raised, "a module that repeats a part name raises ValueError")
    finally:
        path.unlink(missing_ok=True)
        cache = Path(modules.__file__).parent / "__pycache__"
        for item in cache.glob("zz_clash_probe*"):
            item.unlink()
    for key in [k for k in sys.modules if k.startswith("modules.zz_clash_probe")]:
        del sys.modules[key]
    check("zz_clash_probe" not in [m.__name__.rsplit(".", 1)[-1] for m in modules.discover()], "the probe module is gone")


def main():
    for test in (test_discovery, test_unique_names, test_allowed_pairs_are_real, test_parts_are_valid, test_kinds_and_groups,
                 test_clash_is_detected):
        test()
    print("MODULES OK" if not FAILURES else f"MODULES FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
