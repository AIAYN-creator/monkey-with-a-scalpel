"""Cautery (card t-cautery): a fine electrode in an insulating holder, with an energy limit and a power cut on abort.

Printed: the holder (6 mm bore) and an insulating ring that stands the electrode off the holder (a printed ring is only a stand-in:
the real one must be a heat-resistant material). Bought, as dummies: the electrode (1 mm rod) and its lead. Not placed in the machine
assembly (see _toolkit.py). The power goes through a hardware cut-off and is cut as the abort starts; the model refuses a pulse above
the energy limit.
"""
from build123d import Pos

from ._toolkit import ring, rod, sleeve

TOOL = {"name": "cautery", "tip_z": -25.0, "dummy_mass_g": {"cautery_electrode": 2.0, "cautery_lead": 8.0}}


def cautery_holder():
    return sleeve(6.0)


def cautery_insulator():
    """Ring 10 mm outside, 3 mm bore, 10 mm high. Local frame: from z = 0 to 10."""
    return ring(10.0, 3.0, 10.0)


PARTS = {"cautery_holder": (cautery_holder, "printed"), "cautery_insulator": (cautery_insulator, "printed")}
TOOL_ALLOWED = set()


def assembly():
    return {
        "cautery_holder": (cautery_holder(), "printed"),
        "cautery_insulator": (Pos(0, 0, -12.0) * cautery_insulator(), "printed"),
        "cautery_electrode": (rod(1.0, -25.0, 40.0), "dummy"),
        "cautery_lead": (rod(2.0, 40.0, 100.0, y=6.0), "dummy"),
    }
