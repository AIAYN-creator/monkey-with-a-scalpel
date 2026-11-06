"""Moving with the X carriage: the X carriage, the Y plate, and the Y rail, screw and motor."""
import params as P
import parts
import system_parts as SP
from build123d import Box, Pos, Rot

ALLOWED = {frozenset(("y_screw", "y_motor"))}


def moving(pose):
    xc = pose.xc
    out = {}
    out["x_carriage"] = (Pos(xc, 0, P.CROSSBEAM_TOP) * SP.carriage("x"), "purchased", "x")
    out["y_plate"] = (Pos(xc, 0, P.CROSSBEAM_TOP + P.CARR_H) * Rot(0, 0, 90) * parts.stage_plate(200.0), "machined", "x")
    y_seat = pose.y_seat
    out["y_rail"] = (Pos(xc, 0, y_seat) * SP.rail(160.0, "y"), "purchased", "x")
    out["y_screw"] = (Pos(xc - 28.0, 0, y_seat + 8.0) * Rot(-90, 0, 0) * Pos(0, 0, -95.0) * SP.screw(190.0), "dummy", "x")
    out["y_motor"] = (Pos(xc - 28.0, -125.0, y_seat + 8.0) * Box(P.N17_FACE, 40, P.N17_FACE), "dummy", "x")
    return out
