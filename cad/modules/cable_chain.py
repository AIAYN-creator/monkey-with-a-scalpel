"""Drag chains for the moving harness (X and Y). Not placed in the assembly yet: the chain route and size are not decided."""
import params as P
from build123d import Box, Pos
from parts import hd, hole


def chain_mount():
    """End bracket for a drag chain (the same part serves the fixed and the moving ends): a foot with two M4 holes
    and a lug for the chain end link with two M3 holes. Chain inner width 20 mm assumed. NOT placed in the
    assembly: the chain route and size are not decided.
    """
    foot = Pos(0, 0, 3.0) * Box(40.0, 30.0, 6.0)
    lug = Pos(0, -10.0, 17.0) * Box(30.0, 8.0, 22.0)
    part = foot + lug
    for x in (-14.0, 14.0):
        part -= hole("z", hd(P.M4_CLEAR), 10, x, 8.0, 3.0)
    for z in (11.0, 23.0):
        part -= hole("y", hd(P.M3_CLEAR), 20, 0.0, -10.0, z)
    return part


PARTS = {"chain_mount": (chain_mount, "printed")}
