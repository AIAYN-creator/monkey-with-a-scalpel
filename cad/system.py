"""The whole system placed in world coordinates, version 0.2, and its checks.

World frame: origin on the top face of the base plate, below the crossbeam; X to the right, Y towards the user,
Z up. The tool hangs on the Z carriage; the phantom stays fixed.

    build_fixed(variant)           parts that never move
    build_moving(variant, ...)     parts that move with x, y, z of the axes (and the wrist angle)

Variants: "fixed" (tool bolted to the Z carriage plate, optional fixed-angle wedge not drawn) and "wrist"
(active wrist, A axis, tilt about X at the plane of the needle hub).
Every position is provisional; the checks below are the only verification.
"""
import math

import modules
import params as P
import parts
import system_parts as SP
from build123d import Cylinder, Location, Pos, Rot
from layout import (  # noqa: F401 - re-exported for build.py and the other scripts
    CARRIAGE_Z_MAX,
    CARRIAGE_Z_MIN,
    HALF,
    HUB_TO_CARRIAGE,
    Z_PATTERN,
    Z_PLATE_CENTRE,
    Z_PLATE_LEN,
    Z_PLATE_PATTERN_X,
    Pose,
    aim,
    camera_layout,
    work_y,
    y_axis,
    y_carriage_face,
)

PETG_DENSITY = 1.27  # g/cm3, typical



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


TOOL_CACHE = {}


def tool_parts(variant):
    if "tool" not in TOOL_CACHE:
        TOOL_CACHE["tool"] = tool_head()
        knob = Rot(-90, 0, 0) * SP.quick_knob()  # axis along +Y, base at y = 0
        TOOL_CACHE["tool"]["quick_knob_1"] = Pos(15.0, -14.0, 75.0) * knob
        TOOL_CACHE["tool"]["quick_knob_2"] = Pos(-15.0, -14.0, 45.0) * knob
    shapes = dict(TOOL_CACHE["tool"])
    return shapes




def build_fixed(variant="fixed", setback=110.0):
    """Parts that never move, from every module. Returns {name: (shape, kind)} with kind in printed, machined, purchased, dummy."""
    return modules.fixed(variant, setback)


def build_moving(variant="fixed", xc=0.0, yc=0.0, zc=CARRIAGE_Z_MIN + HALF, theta=0.0, setback=110.0):
    """Parts that move, from every module plus the tool head. Returns {name: (shape, kind, group)} with group in x, y, z, tool."""
    pose = Pose(variant, xc, yc, zc, theta, setback)
    out = modules.moving(pose)
    tool_frame = Pos(xc, pose.yax, pose.zh) * Rot(theta, 0, 0)
    for name, shape in tool_parts(variant).items():
        kind = "dummy" if name.startswith(("syringe", "actuator")) else "printed"
        out[name] = (tool_frame * shape, kind, "tool")
    return out


def bbox_overlap(a, b, pad=0.5):
    ba, bb = a.bounding_box(), b.bounding_box()
    return (ba.min.X < bb.max.X - pad and bb.min.X < ba.max.X - pad and ba.min.Y < bb.max.Y - pad
            and bb.min.Y < ba.max.Y - pad and ba.min.Z < bb.max.Z - pad and bb.min.Z < ba.max.Z - pad)


def overlap(a, b):
    if not bbox_overlap(a, b):
        return 0.0
    try:
        shared = a & b
        return float(shared.volume) if shared is not None else 0.0
    except Exception:  # noqa: BLE001 - an empty intersection may raise depending on the version
        return 0.0


# pairs of the tool head that touch or overlap by design; the other pairs come from the modules
CORE_ALLOWED = {
    frozenset(("syringe_barrel", "hamilton_clamp")),
    frozenset(("actuator_body", "actuator_shaft")),
    frozenset(("syringe_barrel", "syringe_plunger")),
    frozenset(("syringe_barrel", "syringe_needle")),
    frozenset(("syringe_barrel", "plunger_coupler")),
    frozenset(("syringe_plunger", "plunger_coupler")),
    frozenset(("actuator_shaft", "plunger_coupler")),
    frozenset(("hamilton_clamp", "syringe_needle")),
}
ALLOWED = CORE_ALLOWED | modules.allowed()


def interferences(items, only_cross=None, threshold=0.5):
    """Pairwise overlaps (mm3) among {name: shape}. `only_cross`: (set_a, set_b) to test only between two sets."""
    names = list(items)
    found = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if frozenset((a, b)) in ALLOWED:
                continue
            if only_cross and not ((a in only_cross[0] and b in only_cross[1]) or (a in only_cross[1] and b in only_cross[0])):
                continue
            v = overlap(items[a], items[b])
            if v > threshold:
                found[f"{a} / {b}"] = round(v, 1)
    return found


def segment_solid(p1, p2, radius=0.25):
    d = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
    length = math.sqrt(sum(v * v for v in d))
    return Location(p1) * aim(d) * Pos(0, 0, length / 2) * Cylinder(radius, length)


def line_of_sight(variant, setback=110.0):
    """For each camera, the tip positions (of a grid over the travel) whose line to the camera crosses another part.

    Returns {camera: {"blocked": [...], "total": n, "off_axis_deg": max angle between the optical axis and the line}}.
    """
    cams = camera_layout(variant, setback)
    optical = {"A": (0.0, -math.cos(math.radians(cams["A"]["pitch"])), -math.sin(math.radians(cams["A"]["pitch"]))),
               "B": (-1.0, 0.0, 0.0)}
    fixed = build_fixed(variant, setback)
    result = {}
    for cam in ("A", "B"):
        centre = cams[cam]["centre"]
        blocked, total, worst = [], 0, 0.0
        for xc in (-HALF, 0.0, HALF):
            for yc in (-HALF, 0.0, HALF):
                for zt in (P.TIP_MIN, P.TIP_MIN + HALF, P.TIP_MIN + P.TRAVEL):
                    zc = zt + 30.0 + HUB_TO_CARRIAGE
                    moving = build_moving(variant, xc, yc, zc, 0.0, setback)
                    tip = (xc, y_axis(yc, variant, setback), zt)
                    # start 1 mm along the line, so the needle itself and the gel it sits in are not counted
                    d = [centre[i] - tip[i] for i in range(3)]
                    n = math.sqrt(sum(v * v for v in d))
                    start = tuple(tip[i] + d[i] / n * 1.5 for i in range(3))
                    seg = segment_solid(start, centre)
                    obstacles = {k: v[0] for k, v in moving.items() if k not in ("syringe_needle",)}
                    obstacles.update({k: v[0] for k, v in fixed.items() if k in ("phantom_tray", "control_panel", "crossbeam")})
                    hit = [k for k, s in obstacles.items() if overlap(seg, s) > 1e-4]
                    total += 1
                    cosang = sum(d[i] * optical[cam][i] for i in range(3)) / n
                    worst = max(worst, math.degrees(math.acos(max(-1.0, min(1.0, -cosang)))))
                    if hit:
                        blocked.append({"tip": [xc, round(tip[1], 1), zt], "by": hit})
        result[cam] = {"blocked": blocked, "total": total, "off_axis_deg": round(worst, 1)}
    return result


def sweep_wrist(setback, angles=(-P.WRIST_MAX, 0.0, P.WRIST_MAX), zcs=None, positions=((0.0, 0.0),)):
    """Interferences of the swinging tool with everything else, over the wrist angles, three heights of Z and the given (x, y)."""
    zcs = zcs or (CARRIAGE_Z_MIN, CARRIAGE_Z_MIN + HALF, CARRIAGE_Z_MAX)
    fixed = build_fixed("wrist", setback)
    found = {}
    for xc, yc in positions:
        for zc in zcs:
            for th in angles:
                moving = build_moving("wrist", xc, yc, zc, th, setback)
                swing = {k for k, v in moving.items() if v[2] == "tool"}
                items = {k: v[0] for k, v in moving.items()}
                items.update({k: v[0] for k, v in fixed.items()})
                others = set(items) - swing
                for k, v in interferences(items, only_cross=(swing, others)).items():
                    found[f"x={xc:+.0f} y={yc:+.0f} zc={zc:.0f} A={th:+.0f}: {k}"] = v
    return found


def sweep_travel(variant="fixed", setback=110.0, margin=4.0, zc_low=None):
    """Interferences of the moving parts with the fixed ones at the corners of the travel, plus `margin` (hard stops).

    `zc_low` is the lowest carriage height tried (default: the lowest one minus `margin`). With the active wrist the lowest
    height is WRIST_MIN_ZC, because the yoke arms touch the phantom below it.
    """
    fixed = build_fixed(variant, setback)
    found = {}
    half = HALF + margin
    for xc in (-half, half):
        for yc in (-half, half):
            for zc in (CARRIAGE_Z_MIN - margin if zc_low is None else zc_low, CARRIAGE_Z_MAX + margin):
                moving = build_moving(variant, xc, yc, zc, 0.0, setback)
                items = {k: v[0] for k, v in moving.items()}
                items.update({k: v[0] for k, v in fixed.items()})
                for k, v in interferences(items, only_cross=(set(moving), set(fixed))).items():
                    found[f"x={xc:+.0f} y={yc:+.0f} zc={zc:.0f}: {k}"] = v
    return found


# With the active wrist the arms of the yoke straddle the needle (27 to 35 mm each side) at the height of the hub plane, 30 mm above
# the tip, so below this tip height they touch the phantom block (found by sweeping the corners of the travel with the wrist, which
# the build did not do before). The firmware has to keep the tip above it and the bottom stop of Z has to sit there.
WRIST_MIN_TIP = P.TIP_MIN + 2.0
WRIST_MIN_ZC = WRIST_MIN_TIP + 30.0 + HUB_TO_CARRIAGE

# tilting the wrist to +30 degrees with the needle deeper than this hits the phantom with the cradle (found by the sweep)
WRIST_TILT_MIN_TIP = 20.0 + P.HEATER_T  # 8 mm below the phantom surface (28 mm without a heater plate)


def sweep_wrist_all(setback):
    """The wrist swing over the whole range and the corners of the XY travel, with the rule that A = +30 needs the tip at or above
    WRIST_TILT_MIN_TIP and the tool never goes below WRIST_MIN_ZC."""
    positions = ((0.0, 0.0), (-HALF, -HALF), (HALF, -HALF), (-HALF, HALF), (HALF, HALF))
    zc_rule = WRIST_TILT_MIN_TIP + 30.0 + HUB_TO_CARRIAGE
    found = sweep_wrist(setback, angles=(-P.WRIST_MAX, 0.0, P.WRIST_MAX), zcs=(zc_rule, CARRIAGE_Z_MIN + HALF, CARRIAGE_Z_MAX),
                        positions=positions)
    found.update(sweep_wrist(setback, angles=(-P.WRIST_MAX, 0.0), zcs=(WRIST_MIN_ZC,), positions=positions))
    return found
