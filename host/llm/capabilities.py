"""What the LLM is allowed to ask for: a closed list of capabilities, each with typed parameters and ranges.

The language model never sends a G-code line or a raw command: it proposes steps that name a capability from this table and give its
parameters. The table is built from the machine's own limits and from the tool descriptors (tools/<name>/descriptor.yaml), so the text
that describes the capabilities to the model, the validator and the executor all read the same data. Numbers are provisional until
the machine is measured (the travel will change with the card mech-recorrido).
"""
from toolsim import load_descriptor
from toolsim.base import ROOT

MACHINE = {"x": (-50.0, 50.0), "y": (-50.0, 50.0), "z": (0.0, 100.0), "feed": (0.1, 20.0)}  # tip position (mm) and speed (mm/s)
STEP_MS = 2000  # simulated time that each step takes at least (the cautery gap, for one)

# machine capabilities: name -> {param: (min, max) or "text"}
MACHINE_CAPS = {
    "home": {},
    "park": {},
    "stop": {},
    "move_to": {"x": MACHINE["x"], "y": MACHINE["y"], "z": MACHINE["z"], "feed": MACHINE["feed"]},
    "mount_tool": {"tool": "text"},  # a person changes the tool at rest (card t-mount); the plan only asks
    "tool_on": {},
    "tool_off": {},
}

# tool capabilities: (tool, capability) -> {param: (min, max) or "text"}. The ranges here are only the sanity range of the unit; the
# limits of each tool come from its descriptor and are enforced by the model of the tool when the plan is dry-run.
TOOL_CAPS = {
    ("injector", "prime"): {"volume_ul": (0.01, 10.0)},
    ("injector", "inject"): {"volume_ul": (0.01, 10.0), "rate_ul_s": (0.01, 10.0)},
    ("injector", "wash"): {"cycles": (1, 10)},
    ("probe", "touch"): {},
    ("probe", "find_surface"): {"approach_mm_s": (0.05, 10.0)},
    ("probe", "find_landmark"): {"x": MACHINE["x"], "y": MACHINE["y"]},
    ("scalpel", "set_depth_stop"): {"depth_mm": (0.05, 10.0)},
    ("scalpel", "change_blade"): {},
    ("scalpel", "incise"): {"length_mm": (0.1, 100.0), "depth_mm": (0.05, 10.0), "feed_mm_s": (0.05, 20.0)},
    ("scalpel", "cut_line"): {"x2": MACHINE["x"], "y2": MACHINE["y"], "depth_mm": (0.05, 10.0), "feed_mm_s": (0.05, 20.0)},
    ("drill", "set_depth_stop"): {"depth_mm": (0.05, 10.0)},
    ("drill", "drill"): {"depth_mm": (0.05, 10.0), "feed_mm_s": (0.01, 5.0), "rpm": (1000, 50000)},
    ("fluid", "aspirate"): {"volume_ul": (0.1, 500.0), "rate_ul_s": (0.1, 50.0)},
    ("fluid", "irrigate"): {"volume_ul": (0.1, 500.0), "rate_ul_s": (0.1, 50.0)},
    ("fluid", "dispense_adhesive"): {"volume_ul": (0.1, 50.0), "rate_ul_s": (0.1, 10.0)},
    ("fluid", "purge"): {"volume_ul": (1.0, 500.0)},
    ("gripper", "grip"): {"item": "text", "width_mm": (0.1, 20.0), "force_n": (0.01, 10.0)},
    ("gripper", "release"): {},
    ("gripper", "place_implant"): {},
    ("cautery", "coagulate"): {"power_w": (0.1, 10.0), "pulse_ms": (1, 2000)},
    ("sensor", "dark_reference"): {},
    ("sensor", "read_fluorescence"): {"integration_ms": (1, 10000)},
    ("sensor", "read_photometry"): {"integration_ms": (1, 10000)},
}


def all_capabilities():
    """{full name: schema}. Tool capabilities are written `tool.capability`."""
    caps = dict(MACHINE_CAPS)
    for (tool, cap), schema in TOOL_CAPS.items():
        caps[f"{tool}.{cap}"] = schema
    return caps


def tools():
    return sorted({tool for tool, _ in TOOL_CAPS})


def describe():
    """The text that tells the model what it may ask for: every capability, its parameters with ranges, and the limits of each tool."""
    lines = ["You may only propose steps that name one of these capabilities. Parameters are numbers in mm, mm/s, uL or the unit shown.",
             "Every plan is checked by a program and approved by a person before anything moves. Never ask for anything not listed.", ""]
    for name, schema in all_capabilities().items():
        params = ", ".join(f"{p} {'text' if r == 'text' else f'{r[0]} to {r[1]}'}" for p, r in schema.items()) or "no parameters"
        lines.append(f"- {name}: {params}")
    lines.append("")
    lines.append("Limits of each tool (provisional, from its descriptor):")
    for tool in tools():
        d = load_descriptor(tool)
        limits = ", ".join(f"{k}={v}" for k, v in d.get("limits", {}).items())
        lines.append(f"- {tool}: {limits}; on abort: {d['safe_state']}")
    return "\n".join(lines)


def check_tables():
    """Problems between the tables and the descriptors, for the tests: a capability in one and not in the other."""
    problems = []
    for folder in sorted((ROOT / "tools").glob("*/descriptor.yaml")):
        d = load_descriptor(folder.parent.name)
        have = {cap for (tool, cap) in TOOL_CAPS if tool == d["name"]}
        want = set(d["capabilities"])
        if have != want:
            problems.append(f"{d['name']}: the table has {sorted(have)}, the descriptor {sorted(want)}")
    return problems
