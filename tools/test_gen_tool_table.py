"""Tests of the tool descriptor parser and its rules. Usage, from the repository root:

    python tools/test_gen_tool_table.py
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gen_tool_table as gen

FAILURES = []


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


GOOD = """# a comment
id: 7
name: test_probe
class: probe
mass_g: 80
tip_mm: [0, 0, -12.5]
retract_mm: 10
axes: []
power:
  max_current_a: 0.2
  hw_cutoff: false
  cut_on_abort: false
safe_state: withdraw along the axis
capabilities: [touch]
"""


def descriptor(**changes):
    d = gen.parse(GOOD)
    d.update(changes)
    return d


def rejected(d):
    try:
        gen.validate(copy.deepcopy(d), "test")
    except gen.DescriptorError:
        return True
    return False


def test_parser():
    print("parser")
    d = gen.parse(GOOD)
    check(d["id"] == 7 and d["name"] == "test_probe" and d["tip_mm"] == [0, 0, -12.5], "numbers, text and lists are read")
    check(d["axes"] == [] and d["power"]["hw_cutoff"] is False and d["power"]["max_current_a"] == 0.2, "empty lists, booleans and nesting")
    check(d["safe_state"] == "withdraw along the axis" and d["capabilities"] == ["touch"], "plain text and a list of names")
    for bad in ("id 7", "  id: 7", "power:\n    deep: 1", "id: 7\n  stray: 1"):
        try:
            gen.parse(bad)
            check(False, f"{bad!r} must be rejected")
        except gen.DescriptorError:
            pass


def test_validation():
    print("validation")
    check(not rejected(descriptor()), "a good descriptor is accepted")
    check(rejected({k: v for k, v in descriptor().items() if k != "safe_state"}), "a missing field is rejected")
    for field, value in (("id", 0), ("id", 70000), ("name", "Bad Name"), ("class", "laser"), ("mass_g", 0), ("mass_g", 5000),
                         ("tip_mm", [1, 2]), ("retract_mm", 0), ("retract_mm", 500), ("axes", ["Q"]), ("axes", ["XY"]),
                         ("safe_state", " "), ("capabilities", [])):
        check(rejected(descriptor(**{field: value})), f"{field}={value!r} is rejected")
    power = dict(descriptor()["power"])
    check(rejected(descriptor(power={**power, "hw_cutoff": "yes"})), "a non-boolean flag is rejected")
    check(rejected(descriptor(power={**power, "max_current_a": 9})), "too much current is rejected")
    check(rejected(descriptor(power={"max_current_a": 1.0})), "a power block with missing keys is rejected")


def test_safety_rules():
    print("safety rules")
    power = dict(descriptor()["power"])
    check(rejected(descriptor(**{"class": "drill"}, power={**power, "max_current_a": 2.0, "hw_cutoff": True, "cut_on_abort": False})),
          "a drill that does not cut its power on abort is rejected")
    check(rejected(descriptor(**{"class": "cautery"}, power={**power, "max_current_a": 2.0, "hw_cutoff": True, "cut_on_abort": False})),
          "a cautery that does not cut its power on abort is rejected")
    check(rejected(descriptor(**{"class": "drill"}, power={**power, "max_current_a": 2.0, "hw_cutoff": False, "cut_on_abort": True})),
          "a drill without a hardware cut-off is rejected")
    check(rejected(descriptor(**{"class": "cutter"}, power={**power, "max_current_a": 1.0, "hw_cutoff": False})),
          "a cutter drawing more than 0.5 A without a hardware cut-off is rejected")
    check(not rejected(descriptor(**{"class": "drill"}, power={**power, "max_current_a": 2.0, "hw_cutoff": True, "cut_on_abort": True})),
          "a drill with both protections is accepted")


def test_real_descriptors_and_table():
    print("the committed descriptors and table")
    descriptors = gen.load_all()
    check(any(d["name"] == "injector" for d in descriptors), "the injector descriptor loads")
    check(gen.main(["--check"]) == 0, "the committed firmware table matches the descriptors")
    ids = [d["id"] for d in descriptors]
    check(ids == sorted(ids) and len(ids) == len(set(ids)), "ids are unique and the table is sorted by id")
    text = gen.render(descriptors)
    check("kToolTable" in text and "Do not edit" in text, "the generated header says it is generated")


def main():
    for test in (test_parser, test_validation, test_safety_rules, test_real_descriptors_and_table):
        test()
    print("TOOL TABLE TESTS OK" if not FAILURES else f"TOOL TABLE TESTS FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
