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

import params as P
import parts
import system_parts as SP
from build123d import Box, Cylinder, Location, Pos, Rot

PETG_DENSITY = 1.27  # g/cm3, typical
HUB_TO_CARRIAGE = 93.0  # z of the carriage centre above the needle hub plane (interface at 60 + 33)
Z_PATTERN = 265.0  # world z of the Z plate pattern centre
Z_PLATE_LEN = 200.0
Z_PLATE_PATTERN_X = 75.0
Z_PLATE_CENTRE = Z_PATTERN - Z_PLATE_PATTERN_X
CARRIAGE_Z_MIN = P.TIP_MIN + 30.0 + HUB_TO_CARRIAGE  # needle tip lowest
CARRIAGE_Z_MAX = CARRIAGE_Z_MIN + P.TRAVEL
HALF = P.TRAVEL / 2


def y_carriage_face(yc):
    """World y of the face of the Z carriage (where the printed carriage plate starts)."""
    return yc + P.ARM_REACH + 3.0 + 6.0 + P.CARR_H


def y_axis(yc, variant, setback):
    """World y of the needle axis."""
    face = y_carriage_face(yc)
    return face + (26.0 if variant == "fixed" else setback + 12.0)


def work_y(variant, setback):
    return y_axis(0.0, variant, setback)


def aim(direction):
    """Rotation that takes +Z to `direction`."""
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    return Rot(0, 0, math.degrees(math.atan2(dy, dx))) * Rot(0, math.degrees(math.acos(dz / length)), 0)


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
        TOOL_CACHE["cradle"] = SP.wrist_cradle()
        knob = Rot(-90, 0, 0) * SP.quick_knob()  # axis along +Y, base at y = 0
        TOOL_CACHE["tool"]["quick_knob_1"] = Pos(15.0, -14.0, 75.0) * knob
        TOOL_CACHE["tool"]["quick_knob_2"] = Pos(-15.0, -14.0, 45.0) * knob
    shapes = dict(TOOL_CACHE["tool"])
    if variant == "wrist":
        shapes["wrist_cradle"] = TOOL_CACHE["cradle"]
    return shapes


def camera_layout(variant, setback):
    """Positions of the two cameras (centres) and the pitch of the oblique one."""
    wy = work_y(variant, setback)
    pitch = 40.0
    return {
        "A": {"centre": (0.0, wy + 95.0, 135.0), "pitch": pitch},
        "B": {"centre": (152.5, wy, 45.0)},
    }


def build_fixed(variant="fixed", setback=110.0):
    """Parts that never move. Returns {name: (shape, kind)} with kind in printed, machined, purchased, dummy."""
    wy = work_y(variant, setback)
    front = wy + 170.0
    out = {}
    tray_holes = [(sx * 40.0, wy + sy * 40.0) for sx in (-1, 1) for sy in (-1, 1)]
    out["base_plate"] = (SP.base_plate(front + 130.0, -130.0, tray_holes), "machined")
    for sign in (-1, 1):
        out[f"upright_{'r' if sign > 0 else 'l'}"] = (Pos(sign * P.UPRIGHT_X, 0, 0) * SP.profile(P.CROSSBEAM_TOP), "purchased")
    span = 2 * (P.UPRIGHT_X - P.PROFILE / 2)
    out["crossbeam"] = (Pos(-span / 2, 0, P.CROSSBEAM_TOP - P.PROFILE / 2) * SP.profile(span, "x"), "purchased")
    out["x_rail"] = (Pos(0, 0, P.CROSSBEAM_TOP) * SP.rail(200.0, "x"), "purchased")
    # X drive: motor against the left upright, screw behind the crossbeam (nut linkage not drawn)
    ys, zs = -35.0, P.CROSSBEAM_TOP - 10.0
    out["x_screw"] = (Pos(0, ys, zs) * Rot(0, 90, 0) * Pos(0, 0, -105.0) * SP.screw(210.0), "dummy")
    out["x_motor"] = (Pos(-P.UPRIGHT_X + P.PROFILE / 2 + 20.0, ys, zs) * Box(40, P.N17_FACE, P.N17_FACE), "dummy")
    out["electronics_box"] = (Pos(0, -72.0, 0) * SP.electronics_box(), "dummy")
    out["control_panel"] = (Pos(-130.0, wy + 130.0, 0) * SP.control_panel(), "printed")
    out["phantom_tray"] = (Pos(0, wy, 0) * parts.phantom_tray(), "printed")
    out["phantom_block"] = (Pos(0, wy, 0) * SP.phantom_block(), "dummy")
    # X limit switches on the crossbeam, facing the carriage
    for sign in (-1, 1):
        tag = "r" if sign > 0 else "l"
        rot = Rot(0, 0, 90 * sign)
        out[f"x_switch_bracket_{tag}"] = (Pos(sign * 112.0, 0, P.CROSSBEAM_TOP) * rot * SP.limit_switch_bracket(), "printed")
        out[f"x_switch_{tag}"] = (Pos(sign * 112.0, 0, P.CROSSBEAM_TOP) * rot * Pos(0, -2.8, 13.0) * SP.switch_dummy(), "dummy")
    # cameras
    cams = camera_layout(variant, setback)
    a = cams["A"]
    cx, cy, cz = a["centre"]
    pitch = a["pitch"]
    cp, sp_ = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    tilt_y, tilt_z = cy + cp * 22.5, cz + sp_ * 22.5
    flat_y = tilt_y + 8.0 + 20.0 * math.tan(math.radians(pitch))
    out["cam_a_post"] = (Pos(0, flat_y + 10.0, 0) * SP.profile(cz + 40.0), "purchased")
    out["cam_a_wedge"] = (Pos(0, flat_y, tilt_z) * Rot(0, 0, 180) * SP.camera_wedge(pitch), "printed")
    out["cam_a"] = (Pos(cx, cy, cz) * aim((0.0, -cp, -sp_)) * SP.camera_body(), "dummy")
    bx, by, bz = cams["B"]["centre"]
    out["cam_b_post"] = (Pos(bx + 22.5 + 5.0 + 10.0, by, 0) * SP.profile(120.0), "purchased")
    out["cam_b_plate"] = (Pos(bx + 22.5 + 5.0, by, bz) * Rot(0, 0, 90) * parts.camera_plate(), "printed")
    out["cam_b"] = (Pos(bx, by, bz) * aim((-1.0, 0.0, 0.0)) * SP.camera_body(), "dummy")
    return out


def build_moving(variant="fixed", xc=0.0, yc=0.0, zc=CARRIAGE_Z_MIN + HALF, theta=0.0, setback=110.0):
    """Parts that move. Returns {name: (shape, kind, group)} with group in x, y, z, tool."""
    y_car = y_carriage_face(yc)
    y_pf = y_car - P.CARR_H  # front face of the Z plate
    y_leg = yc + P.ARM_REACH + 3.0  # front face of the riser leg
    yax = y_axis(yc, variant, setback)
    zh = zc - HUB_TO_CARRIAGE
    out = {}
    out["x_carriage"] = (Pos(xc, 0, P.CROSSBEAM_TOP) * SP.carriage("x"), "purchased", "x")
    out["y_plate"] = (Pos(xc, 0, P.CROSSBEAM_TOP + P.CARR_H) * Rot(0, 0, 90) * parts.stage_plate(200.0), "machined", "x")
    y_seat = P.CROSSBEAM_TOP + P.CARR_H + 6.0
    out["y_rail"] = (Pos(xc, 0, y_seat) * SP.rail(160.0, "y"), "purchased", "x")
    out["y_screw"] = (Pos(xc - 28.0, 0, y_seat + 8.0) * Rot(-90, 0, 0) * Pos(0, 0, -95.0) * SP.screw(190.0), "dummy", "x")
    out["y_motor"] = (Pos(xc - 28.0, -125.0, y_seat + 8.0) * Box(P.N17_FACE, 40, P.N17_FACE), "dummy", "x")
    out["y_carriage"] = (Pos(xc, yc, y_seat) * SP.carriage("y"), "purchased", "y")
    y_top = y_seat + P.CARR_H
    out["z_riser"] = (Pos(xc, yc, y_top) * SP.z_riser(), "machined", "y")
    z_plate = Pos(xc, y_leg, Z_PLATE_CENTRE) * Rot(270, 0, 270) * parts.stage_plate(Z_PLATE_LEN, Z_PLATE_PATTERN_X)
    out["z_plate"] = (z_plate, "machined", "y")
    z_rot = Rot(270, 0, 270)
    out["z_rail"] = (Pos(xc, y_pf, Z_PLATE_CENTRE) * z_rot * SP.rail(180.0, "x"), "purchased", "y")
    out["z_screw"] = (Pos(xc + 58.0, y_pf + 8.0, 95.0) * SP.screw(240.0), "dummy", "y")
    out["z_motor"] = (Pos(xc + 58.0, y_pf + 8.0, 295.0) * SP.motor17(), "dummy", "y")
    out["z_knob"] = (Pos(xc + 58.0, y_pf + 8.0, 335.0 + 8.0) * SP.z_knob(), "printed", "y")
    out["z_carriage"] = (Pos(xc, y_pf, zc) * z_rot * SP.carriage("x"), "purchased", "z")
    out["z_carriage_plate"] = (Pos(xc, y_car, zc) * parts.z_carriage_plate(), "printed", "z")
    out["z_switch_bracket"] = (
        Pos(xc + 25.0, y_pf, 270.0) * Rot(270, 0, 270) * Rot(0, 0, 180) * SP.limit_switch_bracket(), "printed", "y")
    if variant == "wrist":
        out["wrist_yoke"] = (Pos(xc, yax, zh) * SP.wrist_yoke(setback), "printed", "z")
    tool_frame = Pos(xc, yax, zh) * Rot(theta, 0, 0)
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


# pairs that touch or overlap by design (a needle in a phantom, a screw in its dummy motor...)
ALLOWED = {
    frozenset(("syringe_needle", "phantom_block")),
    frozenset(("syringe_needle", "phantom_tray")),
    frozenset(("syringe_barrel", "hamilton_clamp")),
    frozenset(("actuator_body", "actuator_shaft")),
    frozenset(("syringe_barrel", "syringe_plunger")),
    frozenset(("syringe_barrel", "syringe_needle")),
    frozenset(("syringe_barrel", "plunger_coupler")),
    frozenset(("syringe_plunger", "plunger_coupler")),
    frozenset(("x_screw", "x_motor")),
    frozenset(("y_screw", "y_motor")),
    frozenset(("z_screw", "z_motor")),
    frozenset(("z_screw", "z_knob")),
    frozenset(("z_motor", "z_knob")),
    frozenset(("actuator_shaft", "plunger_coupler")),
    frozenset(("hamilton_clamp", "syringe_needle")),
}


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


def sweep_wrist(setback, angles=(-P.WRIST_MAX, 0.0, P.WRIST_MAX), zcs=None):
    """Interferences of the swinging tool with everything else, over the wrist angles and three heights of Z."""
    zcs = zcs or (CARRIAGE_Z_MIN, CARRIAGE_Z_MIN + HALF, CARRIAGE_Z_MAX)
    fixed = build_fixed("wrist", setback)
    found = {}
    for zc in zcs:
        for th in angles:
            moving = build_moving("wrist", 0.0, 0.0, zc, th, setback)
            swing = {k for k, v in moving.items() if v[2] == "tool"}
            items = {k: v[0] for k, v in moving.items()}
            items.update({k: v[0] for k, v in fixed.items()})
            others = set(items) - swing
            for k, v in interferences(items, only_cross=(swing, others)).items():
                found[f"zc={zc:.0f} A={th:+.0f}: {k}"] = v
    return found


def sweep_travel(variant="fixed", setback=110.0, margin=4.0):
    """Interferences of the moving parts with the fixed ones at the corners of the travel, plus `margin` (hard stops)."""
    fixed = build_fixed(variant, setback)
    found = {}
    half = HALF + margin
    for xc in (-half, half):
        for yc in (-half, half):
            for zc in (CARRIAGE_Z_MIN - margin, CARRIAGE_Z_MAX + margin):
                moving = build_moving(variant, xc, yc, zc, 0.0, setback)
                items = {k: v[0] for k, v in moving.items()}
                items.update({k: v[0] for k, v in fixed.items()})
                for k, v in interferences(items, only_cross=(set(moving), set(fixed))).items():
                    found[f"x={xc:+.0f} y={yc:+.0f} zc={zc:.0f}: {k}"] = v
    return found


# tilting the wrist to +30 degrees with the needle deeper than this hits the phantom with the cradle (found by the sweep)
WRIST_TILT_MIN_TIP = 20.0


def sweep_wrist_all(setback):
    """The wrist swing over the whole range, with the rule that A = +30 needs the tip at or above WRIST_TILT_MIN_TIP."""
    zc_rule = WRIST_TILT_MIN_TIP + 30.0 + HUB_TO_CARRIAGE
    found = sweep_wrist(setback, angles=(-P.WRIST_MAX, 0.0, P.WRIST_MAX), zcs=(zc_rule, CARRIAGE_Z_MIN + HALF, CARRIAGE_Z_MAX))
    found.update(sweep_wrist(setback, angles=(-P.WRIST_MAX, 0.0), zcs=(CARRIAGE_Z_MIN,)))
    return found
