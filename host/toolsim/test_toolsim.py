"""Tests of the simulated tool models and the wash station. Usage, from the repository root:

    python host/toolsim/test_toolsim.py

Every tool is checked for the same things (its operations are its descriptor's capabilities, it needs power, an abort leaves it in
its safe state) and then for its own rules (the limits that its descriptor declares). Exit code 1 on a failure.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toolsim import MODELS, ToolFault, WashStation, build, load_descriptor
from toolsim.base import ROOT

FAILURES = []


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


def refused(code, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ToolFault as fault:
        return fault.code == code
    return False


def powered(name, **kw):
    tool = build(name, **kw)
    tool.power_on()
    return tool


def test_registry():
    print("every descriptor has a model, and the operations are the capabilities")
    folders = sorted(p.parent.name for p in (ROOT / "tools").glob("*/descriptor.yaml"))
    check(folders == sorted(MODELS), f"models {sorted(MODELS)} are the descriptors {folders}")
    for name in MODELS:
        tool = build(name)
        check(tool.operations() == sorted(tool.d["capabilities"]), f"{name}: operations {tool.operations()} = capabilities {sorted(tool.d['capabilities'])}")
        check(bool(tool.limits), f"{name}: the descriptor declares its limits")
        check(refused("unknown_capability", tool.run, "no_such_thing"), f"{name}: an unknown capability is refused")
        check(refused("not_powered", tool.run, tool.d["capabilities"][0]), f"{name}: an operation needs TOOL ON")


def test_abort_everywhere():
    print("an abort in the middle of an operation stops it and leaves the safe state")
    cases = {
        "injector": ("inject", {"volume_ul": 1.0, "rate_ul_s": 0.5}, lambda t: t.run("prime", volume_ul=5.0)),
        "probe": ("find_surface", {"surface_z": -5.0, "start_z": 0.0}, None),
        "scalpel": ("incise", {"length_mm": 10.0, "depth_mm": 1.0, "feed_mm_s": 2.0}, lambda t: (t.run("change_blade"), t.run("set_depth_stop", depth_mm=2.0))),
        "drill": ("drill", {"depth_mm": 1.0, "feed_mm_s": 0.2, "rpm": 10000}, lambda t: t.run("set_depth_stop", depth_mm=2.0)),
        "fluid": ("irrigate", {"volume_ul": 50.0, "rate_ul_s": 5.0}, None),
        "gripper": ("grip", {"item": "fibre", "width_mm": 1.0, "force_n": 0.5}, None),
        "cautery": ("coagulate", {"power_w": 1.0, "pulse_ms": 200}, None),
        "sensor": ("read_fluorescence", {"integration_ms": 100, "rate_counts_s": 1000}, lambda t: t.run("dark_reference")),
    }
    for name, (op, args, setup) in cases.items():
        tool = powered(name)
        if setup:
            setup(tool)
        tool.interrupt = lambda t, f: t.abort("test") if f >= 0.5 else None
        check(refused("aborted", tool.run, op, **args), f"{name}: {op} stops with an abort")
        check(tool.aborted, f"{name}: the tool is in the abort state")
        cut = tool.d["power"]["cut_on_abort"]
        check(tool.powered != cut, f"{name}: power after abort is {'off' if cut else 'unchanged'} (cut_on_abort={cut})")
        check(refused("aborted", tool.run, op, **args), f"{name}: it refuses a new operation until the abort is cleared")
        check(refused("aborted", tool.power_on), f"{name}: it cannot be powered during the abort")
        tool.clear()
        tool.interrupt = None
        tool.power_on()
        check(tool.powered, f"{name}: it can be powered after CLEAR")


def test_injector():
    print("injector")
    t = powered("injector")
    expected = (10 / 60) * 2.0 / 3200  # uL per micro-step: 0.1667 uL/mm times 0.625 um
    check(math.isclose(t.ul_per_step, expected, rel_tol=1e-12) and abs(t.ul_per_step * 1000 - 0.104) < 0.001, "0.104 nL per micro-step (hand calculation)")
    t.run("prime", volume_ul=2.0)
    r = t.run("inject", volume_ul=1.0, rate_ul_s=0.5)
    check(abs(r["delivered_ul"] - 1.0) < t.ul_per_step, f"1 uL delivered within one micro-step ({r['delivered_ul']:.5f})")
    check(abs(t.loaded_ul - 1.0) < 2 * t.ul_per_step, "the loaded volume goes down by what was delivered")
    check(refused("limit", t.run, "inject", volume_ul=6.0, rate_ul_s=0.5), "a dose above the 5 uL limit is refused")
    check(refused("limit", t.run, "inject", volume_ul=1.0, rate_ul_s=3.0), "a rate above the limit is refused")
    check(refused("empty", t.run, "inject", volume_ul=3.0, rate_ul_s=0.5), "more than is loaded is refused")
    check(refused("limit", t.run, "prime", volume_ul=11.0), "more than the syringe holds is refused")
    t.run("wash", cycles=3)
    check(t.loaded_ul == 0.0 and t.washed, "a wash empties the syringe")


def test_probe():
    print("probe")
    t = powered("probe", seed=3)
    zs = [t.run("find_surface", surface_z=-5.0, start_z=0.0)["z"] for _ in range(50)]
    mean = sum(zs) / len(zs)
    sd = (sum((z - mean) ** 2 for z in zs) / (len(zs) - 1)) ** 0.5
    check(abs(mean + 5.0) < 0.005, f"the mean of 50 readings is the surface within 5 um ({mean:.4f})")
    check(0.004 < sd < 0.02, f"the spread is about the 10 um declared ({sd * 1000:.1f} um)")
    check(refused("no_contact", t.run, "find_surface", surface_z=-30.0, start_z=0.0), "no contact within the travel is an error")
    check(refused("limit", t.run, "find_surface", surface_z=-5.0, start_z=0.0, approach_mm_s=10.0), "an approach above the speed limit is refused")
    check(refused("limit", t.run, "find_surface", surface_z=5.0, start_z=0.0), "a surface above the start is refused")
    found = t.run("find_landmark", surface_z_at=lambda x, y: -4.0 - 0.01 * x, start_z=0.0, point_xy=(10.0, 0.0))
    check(abs(found["z"] + 4.1) < 0.05, "a landmark reads the surface at its own position")


def test_scalpel():
    print("scalpel")
    t = powered("scalpel")
    check(refused("no_blade", t.run, "incise", length_mm=5.0, depth_mm=1.0, feed_mm_s=2.0), "no cut without a blade")
    t.run("change_blade")
    check(refused("no_depth_stop", t.run, "incise", length_mm=5.0, depth_mm=1.0, feed_mm_s=2.0), "no cut without a depth stop")
    check(refused("limit", t.run, "set_depth_stop", depth_mm=6.0), "a depth stop above 5 mm is refused")
    t.run("set_depth_stop", depth_mm=2.0)
    check(refused("depth", t.run, "incise", length_mm=5.0, depth_mm=2.5, feed_mm_s=2.0), "a cut deeper than the stop is refused")
    check(refused("limit", t.run, "incise", length_mm=50.0, depth_mm=1.0, feed_mm_s=2.0), "a cut longer than the limit is refused")
    check(refused("limit", t.run, "incise", length_mm=5.0, depth_mm=1.0, feed_mm_s=9.0), "a feed above the limit is refused")
    r = t.run("cut_line", points=[(0, 0), (3, 4), (3, 10)], depth_mm=1.5, feed_mm_s=2.0)
    check(abs(r["length_mm"] - 11.0) < 1e-9, "the length of a polyline is the sum of its segments (5 + 6)")
    check(t.guard_closed, "the guard is closed after the cut")
    t.interrupt = lambda tool, f: tool.abort("x") if f >= 0.5 else None
    refused("aborted", t.run, "incise", length_mm=5.0, depth_mm=1.0, feed_mm_s=2.0)
    check(t.guard_closed, "an abort in the cut leaves the guard closed")
    t.clear()
    t.interrupt = None
    t.run("change_blade")
    check(t.depth_stop_mm is None, "a new blade clears the depth stop")


def test_drill():
    print("drill")
    t = powered("drill")
    check(refused("no_depth_stop", t.run, "drill", depth_mm=1.0, feed_mm_s=0.2, rpm=10000), "no drilling without a depth stop")
    t.run("set_depth_stop", depth_mm=1.0)
    check(refused("depth", t.run, "drill", depth_mm=1.5, feed_mm_s=0.2, rpm=10000), "deeper than the stop is refused")
    check(refused("limit", t.run, "drill", depth_mm=0.5, feed_mm_s=0.2, rpm=30000), "a speed above the limit is refused")
    check(refused("limit", t.run, "drill", depth_mm=0.5, feed_mm_s=2.0, rpm=10000), "a feed above the limit is refused")
    r = t.run("drill", depth_mm=0.8, feed_mm_s=0.2, rpm=12000)
    check(abs(r["duration_s"] - 4.0) < 1e-9 and t.rpm == 0, "a hole of 0.8 mm at 0.2 mm/s takes 4 s and the bit stops")
    t.interrupt = lambda tool, f: tool.abort("x") if f >= 0.3 else None
    refused("aborted", t.run, "drill", depth_mm=0.8, feed_mm_s=0.2, rpm=12000)
    check(not t.powered and t.rpm == 0, "an abort cuts the drill power and stops the bit")
    t2 = powered("drill")
    t2.run("set_depth_stop", depth_mm=1.0)
    t2.interrupt = lambda tool, f: tool.power_off() if f >= 0.3 else None  # the power is lost without an abort (the hardware cut-off)
    check(refused("power_lost", t2.run, "drill", depth_mm=0.8, feed_mm_s=0.2, rpm=12000), "a power loss in the middle ends the cut as an error")
    t3 = powered("drill")
    t3.run("set_depth_stop", depth_mm=3.0)
    check(refused("run_time", t3.run, "drill", depth_mm=3.0, feed_mm_s=0.04, rpm=10000), "a run longer than the limit is refused")


def test_fluid():
    print("fluid")
    t = powered("fluid")
    check(abs(t.run("aspirate", volume_ul=40.0, rate_ul_s=10.0)["aspirated_ul"] - 40.0) < 1e-9, "40 uL aspirated")
    check(t.waste_ul == 40.0 and t.valve_closed, "the waste goes up and the valve closes")
    check(refused("limit", t.run, "irrigate", volume_ul=300.0, rate_ul_s=5.0), "a volume above the limit is refused")
    check(refused("pressure", t.run, "irrigate", volume_ul=10.0, rate_ul_s=20.0), "20 uL/s gives 36 kPa, above the 30 kPa limit")
    check(t.run("irrigate", volume_ul=10.0, rate_ul_s=15.0)["irrigated_ul"] == 10.0, "15 uL/s gives 27 kPa and is allowed")
    check(refused("limit", t.run, "dispense_adhesive", volume_ul=6.0, rate_ul_s=1.0), "adhesive above 5 uL is refused")
    t.run("dispense_adhesive", volume_ul=2.0, rate_ul_s=1.0)
    check(abs(t.adhesive_ul - 98.0) < 1e-9, "the adhesive reservoir goes down")
    t.waste_ul = 1990.0
    check(refused("waste_full", t.run, "aspirate", volume_ul=20.0, rate_ul_s=5.0), "a full waste bottle stops the suction")
    t.interrupt = lambda tool, f: tool.abort("x") if f >= 0.5 else None
    refused("aborted", t.run, "irrigate", volume_ul=20.0, rate_ul_s=5.0)
    check(t.valve_closed, "an abort leaves the valve closed")


def test_gripper():
    print("gripper")
    t = powered("gripper")
    check(refused("limit", t.run, "grip", item="fibre", width_mm=12.0, force_n=0.5), "an item wider than the opening is refused")
    check(refused("limit", t.run, "grip", item="fibre", width_mm=1.0, force_n=3.0), "a force above the limit is refused")
    t.run("grip", item="fibre", width_mm=1.0, force_n=0.5)
    check(refused("busy", t.run, "grip", item="other", width_mm=1.0, force_n=0.5), "it holds one item at a time")
    t.abort("x")
    check(t.holding == "fibre", "an abort keeps holding the item (spring-closed jaws)")
    t.clear()
    t.power_on()
    r = t.run("place_implant", target_xyz=(1.0, 2.0, -3.0))
    check(r["placed"] == "fibre" and t.holding is None, "the item is placed and the jaws are free")
    check(refused("empty", t.run, "release"), "nothing to release")
    check(refused("empty", t.run, "place_implant", target_xyz=(0, 0, 0)), "nothing to place")


def test_cautery():
    print("cautery")
    t = powered("cautery")
    check(refused("limit", t.run, "coagulate", power_w=4.0, pulse_ms=100), "a power above the limit is refused")
    check(refused("limit", t.run, "coagulate", power_w=1.0, pulse_ms=400), "a pulse longer than the limit is refused")
    check(refused("energy", t.run, "coagulate", power_w=3.0, pulse_ms=200), "600 mJ is above the 300 mJ per pulse")
    r = t.run("coagulate", power_w=1.5, pulse_ms=200)
    check(abs(r["energy_mj"] - 300.0) < 1e-9 and not t.output_on, "300 mJ delivered and the output is off")
    check(refused("gap", t.run, "coagulate", power_w=1.0, pulse_ms=100), "no second pulse within the gap")
    for _ in range(4):
        t.advance(1000)
        t.run("coagulate", power_w=1.5, pulse_ms=200)
    check(sum(e for _t, e in t.history) == 1500.0, "five pulses of 300 mJ make 1500 mJ")
    t.advance(1000)
    check(refused("budget", t.run, "coagulate", power_w=1.0, pulse_ms=100), "the sixth pulse in a minute is above the budget")
    t.advance(60000)
    t.run("coagulate", power_w=1.0, pulse_ms=100)
    check(True, "after a minute the budget is free again")
    t.interrupt = lambda tool, f: tool.abort("x") if f >= 0.5 else None
    t.advance(2000)
    refused("aborted", t.run, "coagulate", power_w=1.0, pulse_ms=100)
    check(not t.powered and not t.output_on, "an abort cuts the power and the output")
    check(0 < t.history[-1][1] < 100.0, "the energy delivered before the abort is recorded (partial)")


def test_sensor():
    print("sensor")
    t = powered("sensor", seed=5)
    check(refused("no_dark", t.run, "read_fluorescence", integration_ms=100, rate_counts_s=1000), "no reading without a dark reference")
    dark = t.run("dark_reference")["dark_counts"]
    check(abs(dark - 20.0) < 3.0, f"the dark reference is about the 20 counts declared ({dark:.1f})")
    values = [t.run("read_fluorescence", integration_ms=1000, rate_counts_s=500.0)["counts"] for _ in range(40)]
    mean = sum(values) / len(values)
    check(abs(mean - 500.0) < 3.0, f"the mean of 40 readings recovers the signal ({mean:.1f})")
    check(refused("saturated", t.run, "read_photometry", integration_ms=1000, rate_counts_s=70000.0), "a saturated reading is refused")
    check(refused("limit", t.run, "read_photometry", integration_ms=9000, rate_counts_s=1.0), "an integration time above the limit is refused")
    check(not t.light_on, "the light is off after a reading, also after a refusal")


def test_wash():
    print("wash station")
    s = WashStation()
    check(s.cycles_needed(0.02) == 3 and s.cycles_needed(0.10) == 4, "3 flushes at 2 % and 4 dips at 10 % reach 1e-4 (hand calculation)")
    inj = build("injector")
    report = s.wash(inj)
    check(report["clean"] and report["cycles"] == 3, "the injector is washed clean in 3 flushes")
    check(report["steps"][0][0] == "move_to_station" and report["steps"][-1][0] == "retract", "the sequence starts at the station and retracts at the end")
    check(not inj.powered, "the tool is unpowered again after the wash")
    scal = build("scalpel")
    report = s.wash(scal)
    check(report["cycles"] == 4 and [a for a, _d in report["steps"]][1:3] == ["dip", "wipe"], "a scalpel is dipped and wiped")
    check(report["carryover"] <= 1e-4 * (1 + 1e-9), "and ends below the target")
    fl = build("fluid")
    check(s.wash(fl)["clean"] and fl.waste_ul > 0, "the fluid tool is flushed through its own pumps")
    dirty = s.wash(build("probe"), carryover=1e3)
    check(not dirty["clean"], "a very dirty tool is reported as not clean after the standard sequence")
    on = build("probe")
    on.power_on()
    check(refused("powered", s.wash, on), "a powered tool is not washed")
    ab = build("probe")
    ab.abort("x")
    check(refused("aborted", s.wash, ab), "a tool in abort is not washed")
    s2 = WashStation(bath_uses_max=2)
    s2.wash(build("probe"))
    s2.wash(build("probe"))
    check(refused("bath_used", s2.wash, build("probe")), "a used bath is refused")
    s2.change_bath()
    check(s2.wash(build("probe"))["clean"], "a new bath works again")


def test_descriptors():
    print("limits are in the descriptors, not in the code")
    for name in MODELS:
        d = load_descriptor(name)
        for key, value in d.get("limits", {}).items():
            check(isinstance(value, (int, float)) and value > 0, f"{name}.limits.{key} is a positive number")


def main():
    for test in (test_registry, test_abort_everywhere, test_injector, test_probe, test_scalpel, test_drill, test_fluid, test_gripper,
                 test_cautery, test_sensor, test_wash, test_descriptors):
        test()
    print("TOOLSIM OK" if not FAILURES else f"TOOLSIM FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
