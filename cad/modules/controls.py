"""Control panel: emergency stop, ABORT button and pilot LED."""
import params as P
import system_parts as SP
from build123d import Pos
from layout import work_y

PARTS = {"control_panel": (SP.control_panel, "printed")}


def fixed(variant, setback):
    wy = work_y(variant, setback)
    return {"control_panel": (Pos(-130.0 - 0.75 * P.DX, wy + 130.0, 0) * SP.control_panel(), "printed")}
