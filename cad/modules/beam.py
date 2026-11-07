"""Crossbeam as a hollow printed box with four aluminium rods (card mech-viga).

The X axis rides on a beam that spans between the two uprights. Instead of two 2020 profiles joined by plates, the beam is printed in
segments of at most 200 mm (the print volume is 220 mm): a thin-walled rectangular tube with four rod bosses at the corners and a
bulkhead every 50 mm. Four 8 mm aluminium rods run the whole length through the bores of every segment and carry the bending; the closed
tube carries the torsion. Rods and bores leave 0.2 mm of clearance for the epoxy that bonds them; without that bond the section does not
work as one. An end plate of 6 mm on each side closes the beam against the upright, which it holds with two M5 screws into the T-slot.

The section depends on the X travel (params BEAM_W, BEAM_H): 60 x 80 mm for the first prototype, 80 x 100 mm for a large travel, because
the weak point is torsion, not bending (see `python cad/mech_review.py`). The top face is the seat of the X rail: its flatness and the
heat-set inserts for the rail screws are not designed yet.
"""
import math

import params as P
from build123d import Box, Cylinder, Pos, Rot
from parts import hd, hole

WALL = 3.0  # wall of the tube
ROD_D, BORE_D = 8.0, 8.4  # the rod and its bore (0.2 mm of clearance each side)
END_T = 6.0  # end plate
SEG_MAX = 200.0  # longest segment (print volume 220 mm)
BULK, BULK_PITCH = 3.0, 50.0


def section():
    return P.BEAM_W, P.BEAM_H


def rod_offsets():
    """y and z offsets of the rods from the beam axis."""
    w, h = section()
    return w / 2 - WALL - BORE_D / 2, h / 2 - WALL - BORE_D / 2


def span():
    """Distance between the inner faces of the uprights."""
    return 2 * (P.UPRIGHT_X - P.PROFILE / 2)


def beam_length():
    return span() - 2 * END_T


def segment_count():
    return math.ceil(beam_length() / SEG_MAX - 1e-9)


def beam_segment(length):
    """One printed segment along X, centred on the origin: a tube with rod bosses, bulkheads and four bores."""
    w, h = section()
    oy, oz = rod_offsets()
    part = Box(length, w, h) - Box(length + 2.0, w - 2 * WALL, h - 2 * WALL)
    count = math.ceil(length / BULK_PITCH)
    for i in range(count + 1):
        x = -length / 2 + BULK / 2 + i * (length - BULK) / count
        part += Pos(x, 0, 0) * Box(BULK, w - 2 * WALL + 0.2, h - 2 * WALL + 0.2)
    for sy in (-1, 1):
        for sz in (-1, 1):
            part += Pos(0, sy * oy, sz * oz) * Rot(0, 90, 0) * Cylinder(BORE_D / 2 + WALL, length)
    for sy in (-1, 1):
        for sz in (-1, 1):
            part -= Pos(0, sy * oy, sz * oz) * Rot(0, 90, 0) * Cylinder(BORE_D / 2, length + 2.0)
    return part


def beam_end_plate():
    """Plate that closes the end of the beam against an upright: two M5 holes along X, on the axis of the beam."""
    w, h = section()
    part = Pos(0, 0, 0) * Box(END_T, w, h)
    for z in (h / 2 - 10.0, h / 2 - 30.0):
        part -= hole("x", hd(P.M5_CLEAR), END_T + 2, 0, 0, z)
    return part


PARTS = {
    "beam_segment": (lambda: beam_segment(SEG_MAX), "printed"),
    "beam_end_plate": (beam_end_plate, "printed"),
}


def fixed(variant, setback):
    h = section()[1]
    oy, oz = rod_offsets()
    length = beam_length()
    n = segment_count()
    seg = length / n
    z = P.CROSSBEAM_TOP - h / 2
    beam = None
    for i in range(n):
        piece = Pos(-length / 2 + seg * (i + 0.5), 0, z) * beam_segment(seg)
        beam = piece if beam is None else beam + piece
    out = {"crossbeam": (beam, "printed")}
    k = 0
    for sy in (-1, 1):
        for sz in (-1, 1):
            out[f"crossbeam_rod_{k}"] = (Pos(0, sy * oy, z + sz * oz) * Rot(0, 90, 0) * Cylinder(ROD_D / 2, length), "purchased")
            k += 1
    for sign, tag in ((-1, "l"), (1, "r")):
        out[f"beam_end_plate_{tag}"] = (Pos(sign * (length / 2 + END_T / 2), 0, z) * beam_end_plate(), "printed")
    return out
