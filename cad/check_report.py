"""Regression check of the CAD build: compares the report of `build.py` with the committed expectation.

Usage, from the repository root:
    python cad/build.py out
    python cad/check_report.py out/report.json            compare with cad/expected_report.json
    python cad/check_report.py out/report.json --update   rewrite the expectation after a change you meant to make

`build.py` already fails on an interference or a blocked line of sight. This check catches the silent changes: a part that
disappears, grows or changes mass, a camera angle that creeps up, the travel or the tip range that moves. A deliberate change
needs `--update`, so it shows in the diff of the pull request.
"""
import json
import sys
from pathlib import Path

EXPECTED = Path(__file__).resolve().parent / "expected_report.json"
SIZE_TOLERANCE_MM = 0.05
VOLUME_TOLERANCE = 0.01  # relative
ANGLE_TOLERANCE_DEG = 0.2


def summary(report):
    """The fields worth pinning, in a stable form."""
    return {
        "parts": {p["part"]: {"kind": p["kind"], "size_mm": p["size_mm"], "volume_cm3": p["volume_cm3"]} for p in report["parts"]},
        "interference_keys": {key: sorted(found) for key, found in report["interferences"].items()},
        "line_of_sight": {
            variant: {cam: {"blocked": len(res["blocked"]), "total": res["total"], "off_axis_deg": res["off_axis_deg"]}
                      for cam, res in cams.items()}
            for variant, cams in report["line_of_sight"].items()
        },
        "travel_mm": report["travel_mm"],
        "tip_range_z_mm": report["tip_range_z_mm"],
        "wrist_setback_mm": report["wrist_setback_mm"],
        "work_y_mm": report["work_y_mm"],
    }


def compare(expected, actual):
    problems = []
    for name in sorted(set(expected["parts"]) - set(actual["parts"])):
        problems.append(f"part {name} disappeared")
    for name in sorted(set(actual["parts"]) - set(expected["parts"])):
        problems.append(f"part {name} is new")
    for name in sorted(set(expected["parts"]) & set(actual["parts"])):
        e, a = expected["parts"][name], actual["parts"][name]
        if e["kind"] != a["kind"]:
            problems.append(f"part {name} changed kind: {e['kind']} -> {a['kind']}")
        if any(abs(x - y) > SIZE_TOLERANCE_MM for x, y in zip(e["size_mm"], a["size_mm"], strict=True)):
            problems.append(f"part {name} changed size: {e['size_mm']} -> {a['size_mm']}")
        if abs(e["volume_cm3"] - a["volume_cm3"]) > VOLUME_TOLERANCE * max(e["volume_cm3"], 0.01):
            problems.append(f"part {name} changed volume: {e['volume_cm3']} -> {a['volume_cm3']} cm3")
    for key, found in actual["interference_keys"].items():
        if found:
            problems.append(f"interferences in {key}: {found}")
    for key in set(expected["interference_keys"]) - set(actual["interference_keys"]):
        problems.append(f"the check {key} is no longer run")
    for variant, cams in expected["line_of_sight"].items():
        for cam, e in cams.items():
            a = actual["line_of_sight"].get(variant, {}).get(cam)
            if a is None:
                problems.append(f"line of sight {variant} camera {cam} is no longer checked")
            elif a["blocked"] or a["total"] != e["total"] or abs(a["off_axis_deg"] - e["off_axis_deg"]) > ANGLE_TOLERANCE_DEG:
                problems.append(f"line of sight {variant} camera {cam}: {e} -> {a}")
    for key in ("travel_mm", "tip_range_z_mm", "wrist_setback_mm", "work_y_mm"):
        if expected[key] != actual[key]:
            problems.append(f"{key} changed: {expected[key]} -> {actual[key]}")
    return problems


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    actual = summary(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
    if "--update" in argv:
        EXPECTED.write_text(json.dumps(actual, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print("expectation updated:", EXPECTED, f"({len(actual['parts'])} parts)")
        return 0
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    problems = compare(expected, actual)
    for problem in problems:
        print("CHANGED:", problem)
    print("CAD REPORT OK" if not problems else f"CAD REPORT CHANGED: {len(problems)} differences (run with --update if intended)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
