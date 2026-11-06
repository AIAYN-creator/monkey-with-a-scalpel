"""Tool interface: holder of the floating tool connector. Not placed in the assembly yet: the connector is not chosen.

The quick-change plate itself (pins, latch, presence sensor) is the job of the t-mount card; the tool head and the
quick knobs still live in system.py until then.
"""
import params as P
from build123d import Box, Pos
from parts import hd, hole


def tool_connector_holder():
    """Holder for the floating 12-circuit connector of the tool head (cable end, strain relief by zip tie). Pocket
    22 x 9 mm assumed; NOT placed in the assembly: the connector is not chosen. The tool position comes from the
    two pins, never from this connector.
    """
    plate = Pos(0, 0, 3.0) * Box(40.0, 20.0, 6.0)
    part = plate - Pos(0, 0, 4.5) * Box(22.4, 9.4, 6.0)
    for x in (-16.0, 16.0):
        part -= hole("z", hd(P.M3_CLEAR), 10, x, 0.0, 3.0)
    part -= Pos(0, 7.5, 3.0) * Box(3.6, 2.2, 10.0)
    return part


PARTS = {"tool_connector_holder": (tool_connector_holder, "printed")}
