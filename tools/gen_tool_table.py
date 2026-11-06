"""Generates the firmware tool table from the tool descriptors, and checks that the committed table is up to date.

Usage, from the repository root:
    python tools/gen_tool_table.py            rewrite firmware/core/tool_table.h
    python tools/gen_tool_table.py --check    exit 1 if the committed table differs or a descriptor is invalid

A descriptor is tools/<name>/descriptor.yaml, written in a small subset of YAML (key: value, one level of nested keys, inline lists)
so that no library is needed. The rules are in tools/README.md.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
TABLE = ROOT / "firmware" / "core" / "tool_table.h"
CLASSES = ("injector", "probe", "cutter", "drill", "fluid", "gripper", "cautery", "sensor", "camera")
AXES = "XYZABP"
REQUIRED = ("id", "name", "class", "mass_g", "tip_mm", "retract_mm", "axes", "power", "safe_state", "capabilities")
POWER_KEYS = ("max_current_a", "hw_cutoff", "cut_on_abort")


class DescriptorError(ValueError):
    pass


def scalar(text):
    text = text.strip()
    if text in ("true", "false"):
        return text == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text.strip("'\"")


def value(text):
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [scalar(item) for item in inner.split(",")] if inner else []
    return scalar(text)


def parse(text):
    """Parses the YAML subset. Raises DescriptorError on anything outside it."""
    result, section = {}, None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #")[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.*)", line.strip())
        if not match:
            raise DescriptorError(f"line {number}: cannot read {raw!r}")
        key, rest = match.groups()
        if indent == 0:
            if rest == "":
                result[key] = {}
                section = key
            else:
                result[key] = value(rest)
                section = None
        elif indent == 2 and section is not None and rest != "":
            result[section][key] = value(rest)
        else:
            raise DescriptorError(f"line {number}: unsupported nesting in {raw!r}")
    return result


def validate(d, source):
    problems = []
    for key in REQUIRED:
        if key not in d:
            problems.append(f"missing {key}")
    if problems:
        raise DescriptorError(f"{source}: " + ", ".join(problems))
    if not isinstance(d["id"], int) or not 1 <= d["id"] <= 65535:
        problems.append("id must be an integer from 1 to 65535")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", str(d["name"])):
        problems.append("name must be lowercase letters, digits and underscores")
    if d["class"] not in CLASSES:
        problems.append(f"class must be one of {CLASSES}")
    if not isinstance(d["mass_g"], (int, float)) or not 0 < d["mass_g"] <= 1000:
        problems.append("mass_g must be between 0 and 1000")
    if not (isinstance(d["tip_mm"], list) and len(d["tip_mm"]) == 3 and all(isinstance(v, (int, float)) for v in d["tip_mm"])):
        problems.append("tip_mm must be three numbers")
    if not isinstance(d["retract_mm"], (int, float)) or not 0 < d["retract_mm"] <= 100:
        problems.append("retract_mm must be between 0 and 100")
    if not (isinstance(d["axes"], list) and all(isinstance(a, str) and a in AXES and len(a) == 1 for a in d["axes"])):
        problems.append(f"axes must be letters among {AXES}")
    power = d["power"]
    if not isinstance(power, dict) or set(power) != set(POWER_KEYS):
        problems.append(f"power needs exactly {POWER_KEYS}")
    else:
        if not isinstance(power["max_current_a"], (int, float)) or not 0 <= power["max_current_a"] <= 5:
            problems.append("power.max_current_a must be between 0 and 5")
        for flag in ("hw_cutoff", "cut_on_abort"):
            if not isinstance(power[flag], bool):
                problems.append(f"power.{flag} must be true or false")
        if power.get("max_current_a", 0) > 0.5 and d["class"] in ("drill", "cautery", "cutter") and power.get("hw_cutoff") is False:
            problems.append("a cutting, drilling or cauterising tool must have a hardware power cut-off (power.hw_cutoff: true)")
        if d["class"] in ("drill", "cautery") and power.get("cut_on_abort") is False:
            problems.append("a drill or a cautery must cut its power on abort (power.cut_on_abort: true)")
    if not str(d["safe_state"]).strip():
        problems.append("safe_state must describe what the tool does on abort")
    if not (isinstance(d["capabilities"], list) and d["capabilities"]):
        problems.append("capabilities must be a non-empty list")
    if problems:
        raise DescriptorError(f"{source}: " + "; ".join(problems))
    return d


def load_all():
    descriptors = []
    for path in sorted(TOOLS.glob("*/descriptor.yaml")):
        descriptors.append(validate(parse(path.read_text(encoding="utf-8")), str(path.relative_to(ROOT))))
    ids = [d["id"] for d in descriptors]
    names = [d["name"] for d in descriptors]
    if len(ids) != len(set(ids)):
        raise DescriptorError("two descriptors share an id")
    if len(names) != len(set(names)):
        raise DescriptorError("two descriptors share a name")
    if not descriptors:
        raise DescriptorError("there is no descriptor in tools/")
    return sorted(descriptors, key=lambda d: d["id"])


def render(descriptors):
    lines = [
        "// Generated by tools/gen_tool_table.py from tools/*/descriptor.yaml. Do not edit: change the descriptor and regenerate.",
        "#pragma once",
        "",
        '#include "controller.h"',
        "",
        "namespace fw {",
        "",
        "inline constexpr ToolInfo kToolTable[] = {",
    ]
    for d in descriptors:
        mask = sum(1 << AXES.index(a) for a in d["axes"])
        tip = ", ".join(f"{float(v):.3f}" for v in d["tip_mm"])
        lines.append(
            f'    {{{d["id"]}, "{d["name"]}", ToolClass::{d["class"].capitalize()}, {{{tip}}}, {float(d["retract_mm"]):.3f}, {mask}, '
            f'{float(d["power"]["max_current_a"]):.3f}, {str(d["power"]["cut_on_abort"]).lower()}, {str(d["power"]["hw_cutoff"]).lower()}}},'
        )
    lines += ["};", "inline constexpr unsigned kToolTableSize = sizeof(kToolTable) / sizeof(kToolTable[0]);", "", "}  // namespace fw", ""]
    return "\n".join(lines)


def main(argv):
    try:
        text = render(load_all())
    except DescriptorError as error:
        print("DESCRIPTOR ERROR:", error)
        return 1
    if "--check" in argv:
        current = TABLE.read_text(encoding="utf-8").replace("\r\n", "\n") if TABLE.exists() else ""
        if current != text:
            print("firmware/core/tool_table.h is out of date: run python tools/gen_tool_table.py")
            return 1
        print("TOOL TABLE OK")
        return 0
    TABLE.write_text(text, encoding="utf-8")
    print("wrote", TABLE.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
