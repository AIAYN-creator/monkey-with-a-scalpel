"""Work area: the heater plate under the phantom, the phantom tray and the phantom block."""
import params as P
import parts
import system_parts as SP
from build123d import Box, Pos
from layout import work_y

PARTS = {"phantom_tray": (parts.phantom_tray, "printed")}
ALLOWED = {
    frozenset(("syringe_needle", "phantom_block")),
    frozenset(("syringe_needle", "phantom_tray")),
}


def fixed(variant, setback):
    wy = work_y(variant, setback)
    out = {}
    if P.HEATER_T > 0:
        out["heater_plate"] = (Pos(0, wy, P.HEATER_T / 2) * Box(90.0, 90.0, P.HEATER_T), "dummy")
    out["phantom_tray"] = (Pos(0, wy, P.HEATER_T) * parts.phantom_tray(), "printed")
    out["phantom_block"] = (Pos(0, wy, P.HEATER_T) * SP.phantom_block(), "dummy")
    return out
