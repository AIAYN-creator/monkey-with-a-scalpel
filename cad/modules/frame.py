"""Structure: base plate, uprights, crossbeam, the X rail, the X drive and the X limit switches."""
import params as P
import system_parts as SP
from build123d import Box, Pos, Rot
from layout import work_y

PARTS = {
    "base_plate": (lambda: SP.base_plate(480.0, -130.0, [(-40.0, -40.0)]), "machined"),
    "limit_switch_bracket": (SP.limit_switch_bracket, "printed"),
    "limit_flag": (SP.limit_flag, "printed"),
}
ALLOWED = {frozenset(("x_screw", "x_motor"))}


def fixed(variant, setback):
    wy = work_y(variant, setback)
    front = wy + 170.0 + P.DY
    out = {}
    tray_holes = [(sx * 40.0, wy + sy * 40.0) for sx in (-1, 1) for sy in (-1, 1)]
    out["base_plate"] = (SP.base_plate(front + 130.0, -130.0 - P.DY / 2, tray_holes), "machined")
    for sign in (-1, 1):
        out[f"upright_{'r' if sign > 0 else 'l'}"] = (Pos(sign * P.UPRIGHT_X, 0, 0) * SP.profile(P.CROSSBEAM_TOP), "purchased")
    out["x_rail"] = (Pos(0, 0, P.CROSSBEAM_TOP) * SP.rail(200.0 + P.DX, "x"), "purchased")
    # X drive: motor against the left upright, screw behind the crossbeam (nut linkage not drawn)
    ys, zs = -(P.BEAM_W / 2 + 26.0), P.CROSSBEAM_TOP - 10.0
    out["x_screw"] = (Pos(0, ys, zs) * Rot(0, 90, 0) * Pos(0, 0, -105.0 - P.DX / 2) * SP.screw(210.0 + P.DX), "dummy")
    out["x_motor"] = (Pos(-P.UPRIGHT_X + P.PROFILE / 2 + 20.0, ys, zs) * Box(40, P.N17_FACE, P.N17_FACE), "dummy")
    # X limit switches on the crossbeam, facing the carriage
    for sign in (-1, 1):
        tag = "r" if sign > 0 else "l"
        rot = Rot(0, 0, 90 * sign)
        out[f"x_switch_bracket_{tag}"] = (Pos(sign * (112.0 + P.DX / 2), 0, P.CROSSBEAM_TOP) * rot * SP.limit_switch_bracket(), "printed")
        out[f"x_switch_{tag}"] = (Pos(sign * (112.0 + P.DX / 2), 0, P.CROSSBEAM_TOP) * rot * Pos(0, -2.8, 13.0) * SP.switch_dummy(), "dummy")
    return out
