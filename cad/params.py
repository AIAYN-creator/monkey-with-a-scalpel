"""Parameters of the provisional CAD, version 0.1.

Every value has a source tag, kept in SOURCE:
  catalog   taken from the Hamilton reference guide (page in the note)
  typical   typical catalogue value of a standard part; verify against the datasheet of the part you buy
  assumed   assumption of the design; replace with a measurement
  decided   design decision of this version (see the project guides)

Nothing here is a measurement. Do not print from this version: see MEASUREMENTS_BEFORE_PRINTING.
All lengths in millimetres.
"""
import os

SOURCE: dict[str, str] = {}


def p(name: str, value: float, source: str, note: str = ""):
    """Register a parameter with its source and return its value."""
    SOURCE[name] = f"{source}: {note}" if note else source
    return value


# --- printing -----------------------------------------------------------------------------------------
HOLE_COMP = p("HOLE_COMP", 0.2, "assumed", "added to every printed hole diameter; measure with the tolerance coupon")
PRINT_VOLUME = (p("PRINT_X", 220.0, "assumed", "printer not chosen yet"), 220.0, 250.0)
WALL_MIN = p("WALL_MIN", 2.5, "assumed", "minimum wall thickness for structural parts")

# --- fasteners ----------------------------------------------------------------------------------------
M3_CLEAR = p("M3_CLEAR", 3.4, "typical", "M3 clearance hole before compensation")
M4_CLEAR = p("M4_CLEAR", 4.4, "typical", "M4 clearance hole before compensation")
M25_CLEAR = p("M25_CLEAR", 2.7, "typical", "M2.5 clearance hole before compensation")
M5_CLEAR = p("M5_CLEAR", 5.5, "typical", "M5 clearance hole before compensation")
DOWEL_D = p("DOWEL_D", 3.0, "decided", "locating pins of the tool interface")

# --- Hamilton syringe (10 uL, 1700 series, removable needle) -------------------------------------------------
BARREL_OD = p("BARREL_OD", 6.6, "catalog", "p. 80, 10 uL 1700 series")
STROKE = p("STROKE", 60.0, "catalog", "p. 80, plunger stroke")
NEEDLE_LENGTH = p("NEEDLE_LENGTH", 20.0, "decided", "26 ga, 20 mm, blunt point")
NEEDLE_OD = p("NEEDLE_OD", 0.464, "catalog", "p. 119, 26 ga")
BARREL_LENGTH = p("BARREL_LENGTH", 70.0, "assumed", "dimension A of the measurement sheet")
HUB_LENGTH = p("HUB_LENGTH", 10.0, "assumed", "dimension D of the measurement sheet")
BUTTON_D = p("BUTTON_D", 8.0, "assumed", "dimension G of the measurement sheet")
BUTTON_T = p("BUTTON_T", 2.0, "assumed", "dimension H of the measurement sheet")
PLUNGER_OUT = p("PLUNGER_OUT", 5.0, "assumed", "button height above the barrel top with the plunger fully in")
WIRE_SLOT = p("WIRE_SLOT", 3.0, "assumed", "slot that lets the plunger wire through the coupler")

# --- tool interface (decided): 40 mm square plate, 2 dowels + 2 M4 on a 30 mm square -------------------------
IF_SIZE = p("IF_SIZE", 40.0, "decided", "interface plate size")
IF_PITCH = p("IF_PITCH", 30.0, "decided", "hole square of the interface")

# --- standard parts (typical values, verify) ----------------------------------------------------------------
RAIL_PITCH = p("RAIL_PITCH", 25.0, "typical", "size-12 profile rail, hole pitch")
RAIL_W = p("RAIL_W", 12.0, "typical", "size-12 profile rail width")
RAIL_CB_D = p("RAIL_CB_D", 6.0, "typical", "rail counterbore diameter (M3 head)")
CARR_W = p("CARR_W", 27.0, "typical", "size-12 flanged carriage, width")
CARR_L = p("CARR_L", 45.4, "typical", "size-12 flanged carriage, length")
CARR_B = p("CARR_B", 20.0, "typical", "carriage hole spacing across")
CARR_C = p("CARR_C", 20.0, "typical", "carriage hole spacing along")
NUT_FLANGE_D = p("NUT_FLANGE_D", 22.0, "typical", "T8 flanged nut, flange diameter")
NUT_BC = p("NUT_BC", 16.0, "typical", "T8 flanged nut, bolt circle diameter")
NUT_BORE = p("NUT_BORE", 10.5, "typical", "T8 nut body diameter 10 + clearance")
SCREW_OFFSET = p("SCREW_OFFSET", 22.0, "assumed", "distance from the rail axis to the screw axis")
N17_FACE = p("N17_FACE", 42.3, "typical", "NEMA 17 face")
N17_HOLES = p("N17_HOLES", 31.0, "typical", "NEMA 17 hole spacing")
N17_PILOT = p("N17_PILOT", 22.0, "typical", "NEMA 17 pilot diameter")
N11_FACE = p("N11_FACE", 28.2, "typical", "NEMA 11 face")
N11_HOLES = p("N11_HOLES", 23.0, "typical", "NEMA 11 hole spacing")
N11_PILOT = p("N11_PILOT", 22.0, "typical", "NEMA 11 pilot diameter")
N11_LENGTH = p("N11_LENGTH", 45.0, "assumed", "NEMA 11 captive actuator body length")
ACT_SHAFT_D = p("ACT_SHAFT_D", 4.0, "assumed", "captive actuator shaft diameter")
ACT_OFFSET = p("ACT_OFFSET", 16.0, "decided", "distance from the syringe axis to the actuator axis")
BEARING_OD = p("BEARING_OD", 22.0, "typical", "608 bearing outer diameter")
BEARING_W = p("BEARING_W", 7.0, "typical", "608 bearing width")
BEARING_ID = p("BEARING_ID", 8.0, "typical", "608 bearing bore")
CAM_THREAD = p("CAM_THREAD", 6.6, "typical", "1/4-20 clearance hole")
PHANTOM_BOX = p("PHANTOM_BOX", 60.0, "assumed", "container footprint, square")

# --- layout (decided) --------------------------------------------------------------------------------------
# Useful travel per axis, total, in mm. 100 each is the first prototype; a travel study sets other values with the environment variable
# VERNIER_TRAVEL="x,y,z" (card mech-recorrido). Rails, plates, screws, the frame and the base follow from these numbers.
_TRAVEL = os.environ.get("VERNIER_TRAVEL")
_XYZ = tuple(float(v) for v in _TRAVEL.split(",")) if _TRAVEL else (100.0, 100.0, 100.0)
TRAVEL_X = p("TRAVEL_X", _XYZ[0], "decided", "useful travel of X, total")
TRAVEL_Y = p("TRAVEL_Y", _XYZ[1], "decided", "useful travel of Y, total")
TRAVEL_Z = p("TRAVEL_Z", _XYZ[2], "decided", "useful travel of Z, total")
TRAVEL = TRAVEL_Z  # the vertical travel, as the name was used before there was one per axis
DX, DY, DZ = TRAVEL_X - 100.0, TRAVEL_Y - 100.0, TRAVEL_Z - 100.0  # growth over the first prototype
BEAM_W = p("BEAM_W", 60.0 if DX <= 100.0 else 80.0, "decided", "width (Y) of the printed hollow crossbeam; torsion decides it")
BEAM_H = p("BEAM_H", BEAM_W + 20.0, "decided", "height (Z) of the printed hollow crossbeam; its top face is the X rail seat")
CLAMP_Z = p("CLAMP_Z", 12.0, "decided", "height of the clamp centre above the needle hub plane")


# --- system layout, version 0.2 (decided; heights follow from the tool head and the travel) -----------------
PROFILE = p("PROFILE", 20.0, "typical", "2020 aluminium profile, square side")
RAIL_H = p("RAIL_H", 8.0, "typical", "size-12 rail height")
CARR_H = p("CARR_H", 13.0, "typical", "size-12 carriage total height above the rail seat")
BASE_X = p("BASE_X", 460.0 + 2 * DX, "decided", "base plate, X")
BASE_Y = p("BASE_Y", 380.0 + DY, "decided", "base plate, Y")
BASE_T = p("BASE_T", 10.0, "assumed", "base plate thickness (aluminium or plywood for the first prototype)")
UPRIGHT_X = p("UPRIGHT_X", 200.0 + DX, "decided", "uprights at x = +/- this; the X rail is travel + 100")
CROSSBEAM_TOP = p("CROSSBEAM_TOP", 253.0 + DZ, "decided", "height of the crossbeam top face above the base plate")
ARM_REACH = p("ARM_REACH", 160.0 + DY, "decided", "forward reach of the Z riser leg from the Y carriage centre; must clear the end of the Y plate at full travel")
HEATER_T = p("HEATER_T", 8.0, "assumed", "heater plate under the phantom tray (0 if there is none); raises the phantom and the lowest tip height")
PH_HEIGHT = p("PH_HEIGHT", 25.0, "assumed", "phantom block height")
TIP_MIN = p("TIP_MIN", 13.0 + HEATER_T, "decided", "lowest needle-tip height above the base plate (15 mm below the phantom top, which sits on the heater plate)")
WRIST_MAX = p("WRIST_MAX", 30.0, "decided", "maximum tilt of the active wrist, degrees")
CAM_BODY = (p("CAM_W", 30.0, "assumed", "camera body, width and height"), 30.0, 45.0)
SWITCH_L = p("SWITCH_L", 20.0, "typical", "micro limit switch body length")
SWITCH_W = p("SWITCH_W", 6.4, "typical", "micro limit switch body width")
SWITCH_H = p("SWITCH_H", 10.2, "typical", "micro limit switch body height")
SWITCH_HOLE_PITCH = p("SWITCH_HOLE_PITCH", 9.5, "typical", "micro limit switch mounting hole spacing")
ESTOP_D = p("ESTOP_D", 22.3, "typical", "22 mm mushroom emergency stop, panel hole")
ABORT_D = p("ABORT_D", 16.2, "typical", "16 mm push button, panel hole")
LED_D = p("LED_D", 8.2, "typical", "8 mm indicator, panel hole")

# --- microscope and specimen fixture (cards t-micro and fix-mouse; all assumed) ----------------------------------
MICRO_D = p("MICRO_D", 32.0, "assumed", "USB microscope body diameter")
MICRO_L = p("MICRO_L", 110.0, "assumed", "USB microscope body length")
MICRO_WD = p("MICRO_WD", 100.0, "assumed", "working distance from the lens to the target; a long-working-distance objective is needed so the lens clears the tool at the end of the travel")
MICRO_FOV = p("MICRO_FOV", 12.0, "assumed", "width of the microscope field of view at the working distance")
MICRO_Z = p("MICRO_Z", 55.0, "assumed", "height of the microscope axis above the base plate")
FIX_W = p("FIX_W", 26.0, "assumed", "width of the test piece the fixture holds (a head-sized specimen)")
