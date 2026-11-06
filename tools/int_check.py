"""Integration check of the tools (card int-tools). One descriptor per tool is the single source; this script proves that everything
else that depends on it agrees, and that every tool can be mounted, powered, aborted and changed in simulation.

Usage, from the repository root (needs g++ for the simulated controller):
    python tools/int_check.py

For each tool in tools/*/descriptor.yaml it checks:
  1. the firmware table row (id, name, tip, retract, axes, current, hardware cut-off, cut on abort);
  2. the behaviour model in host/toolsim (it builds and enforces the limits of the descriptor);
  3. the capabilities that the LLM interface offers (exactly the capabilities of the descriptor);
  4. the connector assignment of cad/wiring.py and the CAD module cad/modules/tool_<name>.py;
  5. against the real controller core on a simulated plant: mount, ready, power on, home, move, abort (power cut or kept as the descriptor
     says, and back on with the next TOOL ON), tool off and removal; an unknown tool is refused; a change while powered is a fault;
  6. one cycle in which every tool replaces the previous one;
  7. the same cycle as an LLM plan on the simulated world (validator and executor).
Exit code 1 on any failure.
"""
import importlib.util
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
sys.path.insert(0, str(ROOT / "tools"))

import gen_tool_table as gen
from link import CommandRejected, Session, SimTransport, build_simulator
from llm import Approval, Plan, ScriptedHuman, Step, World, execute, validate
from llm.capabilities import TOOL_CAPS
from toolsim import build

FAILURES = []
AXIS_BIT = {letter: 1 << index for index, letter in enumerate(gen.AXES)}


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


def descriptors():
    found = {}
    for path in sorted(gen.TOOLS.glob("*/descriptor.yaml")):
        d = gen.validate(gen.parse(path.read_text(encoding="utf-8")), str(path.relative_to(ROOT)))
        found[d["name"]] = d
    return found


def table_rows():
    """The rows of firmware/core/tool_table.h: {id: (name, tip, retract, axes_mask, current, hw_cutoff, cut_on_abort)}."""
    rows = {}
    pattern = re.compile(r'\{(\d+), "(\w+)", ToolClass::\w+, \{([^}]*)\}, ([\d.]+), (\d+), ([\d.]+), (true|false), (true|false)\}')
    for m in pattern.finditer(gen.TABLE.read_text(encoding="utf-8")):
        tip = tuple(float(v) for v in m.group(3).split(","))
        rows[int(m.group(1))] = (m.group(2), tip, float(m.group(4)), int(m.group(5)), float(m.group(6)), m.group(7) == "true", m.group(8) == "true")
    return rows


def test_static(tools):
    print("descriptors against the firmware table, the models, the LLM interface, the wiring and the CAD")
    rows = table_rows()
    check(set(rows) == {d["id"] for d in tools.values()}, f"the firmware table has exactly the descriptors' ids ({sorted(rows)})")
    spec = importlib.util.spec_from_file_location("wiring", ROOT / "cad" / "wiring.py")
    sys.path.insert(0, str(ROOT / "cad"))
    wiring = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wiring)
    for name, d in tools.items():
        row = rows.get(d["id"])
        if row is None:
            check(False, f"{name}: no row in the firmware table")
            continue
        power = d["power"]
        expected_axes = sum(AXIS_BIT[a] for a in d["axes"])
        check(row[0] == name, f"{name}: firmware row has the name {row[0]}")
        check(all(abs(a - b) < 1e-6 for a, b in zip(row[1], d["tip_mm"], strict=True)), f"{name}: tip offset {row[1]} equals {d['tip_mm']}")
        check(abs(row[2] - d["retract_mm"]) < 1e-6, f"{name}: retract {row[2]} equals {d['retract_mm']}")
        check(row[3] == expected_axes, f"{name}: axes mask {row[3]} equals {expected_axes}")
        check(abs(row[4] - float(power["max_current_a"])) < 1e-6, f"{name}: current {row[4]}")
        check(row[5] == power["hw_cutoff"] and row[6] == power["cut_on_abort"], f"{name}: hardware cut-off and cut on abort agree")
        model = build(name)
        limits = d.get("limits", {})
        check(all(model.limits.get(k) == v for k, v in limits.items()) and len(model.limits) >= len(limits), f"{name}: the model enforces the descriptor limits")
        offered = {cap for tool, cap in TOOL_CAPS if tool == name}
        check(offered == set(d["capabilities"]), f"{name}: the LLM offers {sorted(offered)}, the descriptor lists {sorted(d['capabilities'])}")
        check(name in wiring.TOOL_WIRING, f"{name}: has a connector assignment in cad/wiring.py")
        check((ROOT / "cad" / "modules" / f"tool_{name}.py").exists(), f"{name}: has a CAD module")
    check(not wiring.check(), f"cad/wiring.py --check is clean ({wiring.check()})")


def settle(transport, ticks=3):
    transport.advance(ticks)


def test_controller(tools, exe, tmp):
    print("every tool against the real controller core on a simulated plant")
    for name, d in tools.items():
        transport = SimTransport(exe, require_tool=True)
        session = Session(transport, log_path=tmp / f"{name}.jsonl")
        try:
            settle(transport)
            transport.mount(d["id"])
            settle(transport)
            info = session.tool()
            check(info["tool"] == name and info["id"] == d["id"] and info["ready"] and not info["power"], f"{name}: mounted, known, ready, not powered ({info})")
            session.tool_on()
            settle(transport)
            check(transport.tool_power(), f"{name}: TOOL ON powers it")
            session.home()
            status = session.wait_settled()
            check(status["state"] == "idle" and status["homed"], f"{name}: the machine homes with it")
            session.move(x=5, feed=20)
            session.run_for(300)
            session.abort()
            status = session.wait_settled()
            cut = d["power"]["cut_on_abort"]
            check(status["state"] == "aborted", f"{name}: an abort ends aborted")
            check(transport.tool_power() != cut, f"{name}: after an abort the power is {'cut' if cut else 'kept'}, as the descriptor says")
            session.clear()
            session.tool_on()
            settle(transport)
            check(transport.tool_power(), f"{name}: the next TOOL ON brings the power back")
            session.tool_off()
            settle(transport)
            check(not transport.tool_power(), f"{name}: TOOL OFF cuts the power")
            transport.mount(0)
            settle(transport)
            check(session.status()["state"] != "fault", f"{name}: removing it when off is not a fault")
            # a change while powered is a fault
            transport.mount(d["id"])
            settle(transport)
            session.tool_on()
            settle(transport)
            transport.mount(0)
            settle(transport)
            status = session.status()
            check(status["state"] == "fault" and status["cause"] == "tool" and not transport.tool_power(), f"{name}: removing it while powered is a fault with the power cut")
        finally:
            session.close()
    transport = SimTransport(exe, require_tool=True)
    session = Session(transport, log_path=tmp / "unknown.jsonl")
    try:
        settle(transport)
        transport.mount(max(d["id"] for d in tools.values()) + 1)
        settle(transport)
        check(session.tool()["tool"] == "unknown" and not session.tool()["ready"], "an id that is not in the table is unknown")
        try:
            session.tool_on()
            check(False, "an unknown tool must not be powered")
        except CommandRejected as error:
            check(error.code == "tool", "an unknown tool is refused with tool")
        check(not transport.tool_power(), "and its power stays off")
    finally:
        session.close()


def test_cycle(tools, exe, tmp):
    print("one cycle in which every tool replaces the previous one")
    transport = SimTransport(exe, require_tool=True)
    session = Session(transport, log_path=tmp / "cycle.jsonl")
    try:
        settle(transport)
        for name, d in sorted(tools.items(), key=lambda item: item[1]["id"]):
            transport.mount(d["id"])
            settle(transport)
            check(session.tool()["tool"] == name and session.tool()["ready"], f"{name}: mounted in the cycle")
            session.tool_on()
            settle(transport)
            if not session.status()["homed"]:
                session.home()
                session.wait_settled()
            session.move(x=2, feed=20)
            session.wait_settled()
            session.park()
            status = session.wait_settled()
            check(status["state"] == "idle", f"{name}: parks and is idle")
            session.tool_off()
            settle(transport)
            check(not transport.tool_power(), f"{name}: off before the change")
            transport.mount(0)
            settle(transport)
            check(session.status()["state"] != "fault", f"{name}: the change is not a fault")
    finally:
        session.close()


def test_llm_cycle(tools):
    print("the same cycle as an LLM plan on the simulated world")
    steps = [Step("home")]
    for name, _d in sorted(tools.items(), key=lambda item: item[1]["id"]):
        steps += [Step("mount_tool", {"tool": name}), Step("tool_on"), Step("tool_off"), Step("park")]
    plan = Plan("change every tool", tuple(steps))
    report = validate(plan)
    check(report.ok, f"the validator accepts the cycle ({report.messages()})")
    world = World()
    result = execute(plan, Approval(plan.hash, "check"), world, ScriptedHuman(), _NullLog())
    check(result.status == "done", f"the executor runs the cycle ({result.status}, {result.reason})")


class _NullLog:
    def append(self, **_fields):
        pass


def main():
    tools = descriptors()
    test_static(tools)
    test_llm_cycle(tools)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        try:
            exe = build_simulator(tmp)
        except Exception as error:  # noqa: BLE001 - report any build problem and stop
            print("cannot build the simulated controller:", error)
            return 2
        test_controller(tools, exe, tmp)
        test_cycle(tools, exe, tmp)
    print("TOOLS INTEGRATION OK" if not FAILURES else f"TOOLS INTEGRATION FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
