"""Provisional wiring map: components, connections, cable groups and estimated lengths, checked against the firmware pins.

Usage, from the repository root:
    python cad/wiring.py            print the tables as Markdown
    python cad/wiring.py --check    consistency checks (used by the CI), exit code 1 on a problem
    python cad/wiring.py --diagram out/wiring.png    draw the block diagram (needs Pillow)

Nothing here is a verified design. Lengths come from the provisional CAD parameters plus assumed routes; currents and
connectors are typical values to confirm against the datasheets of what is bought. The mains side and the
motor-power cut-off must be built and reviewed by a qualified person. Pins are read from
firmware/board/controller_board/board_config.h so the map cannot drift from the firmware.
"""
import re
import sys
from pathlib import Path

import params as P

ROOT = Path(__file__).resolve().parents[1]
BOARD_CONFIG = ROOT / "firmware" / "board" / "controller_board" / "board_config.h"
AXES = ["X", "Y", "Z", "A", "B", "P"]


def read_pins():
    """Pin numbers declared in board_config.h, as {name: list or int}."""
    text = BOARD_CONFIG.read_text(encoding="utf-8")
    pins = {}
    for name, body in re.findall(r"constexpr std::array<int, kAxes> (k\w+)\{([^}]*)\}", text):
        pins[name] = [-1 if item.strip() == "kNoPin" else int(item) for item in body.split(",")]
    for name, value in re.findall(r"constexpr int (k\w*(?:Pin|Tx|Rx)\w*) = (\d+);", text):
        pins[name] = int(value)
    return pins


PINS = read_pins()

# --- cables -------------------------------------------------------------------------------------------------------
# Where each thing sits along the route from the electronics box. Lengths in metres, from the CAD parameters.
BOX_TO_UPRIGHT = 0.25  # assumed: the box stands next to an upright
UPRIGHT = P.CROSSBEAM_TOP / 1000
BEAM_END = P.UPRIGHT_X / 1000  # worst case: the far end of the crossbeam
X_CHAIN = P.TRAVEL / 1000 + 0.15  # cable allowance for the X travel plus the bend of the chain
Y_CHAIN = P.TRAVEL / 1000 + 0.15
REACH = (P.ARM_REACH + 100) / 1000  # along the Y plate and the riser to the Z plate
Z_DROP = (P.TRAVEL + 225) / 1000  # down the Z plate to the tool head (head height 225 mm)
SLACK = 1.15  # 15 % for strain relief and service loops
STATIC_X = BOX_TO_UPRIGHT + UPRIGHT + BEAM_END
STATIC_END = BOX_TO_UPRIGHT + UPRIGHT + BEAM_END * 0.1


def metres(value):
    return round(value * SLACK + 0.1, 1)  # plus 0.1 m at the box end


# (id, what, conductors, shielded, moves, length_m, connector at the machine end)
CABLES = [
    ("C1", "X motor (NEMA 17, at the crossbeam end)", 4, True, False, metres(STATIC_END), "4-pin JST-XH or screw terminal"),
    ("C2", "X limit switches, min and max (common ground)", 3, False, False, metres(STATIC_END), "3-pin JST-XH"),
    ("C3", "Y motor (NEMA 17, on the X carriage)", 4, True, True, metres(STATIC_X + X_CHAIN), "4-pin JST-XH"),
    ("C4", "Y limit switches, min and max (common ground)", 3, False, True, metres(STATIC_X + X_CHAIN), "3-pin JST-XH"),
    ("C5", "Z motor (NEMA 17 dual shaft, on the Y carriage)", 4, True, True,
     metres(STATIC_X + X_CHAIN + Y_CHAIN + REACH), "4-pin JST-XH"),
    ("C6", "Z limit switch, top", 2, False, True, metres(STATIC_X + X_CHAIN + Y_CHAIN + REACH), "2-pin JST-XH"),
    ("C7", "Tool head: plunger actuator (NEMA 11) and wrist A and B motors", 12, True, True,
     metres(STATIC_X + X_CHAIN + Y_CHAIN + REACH + Z_DROP), "12-circuit quick-change connector on the backplate"),
    ("C8", "Control panel: e-stop contact, ABORT button, pilot LED (common ground)", 5, False, False, 1.0, "5-pin JST-XH"),
    ("C9", "Camera A (USB)", 4, True, False, 2.0, "USB, cable with ferrite"),
    ("C10", "Camera B (USB)", 4, True, False, 2.0, "USB, cable with ferrite"),
    ("C11", "Host PC to the controller (USB serial)", 4, True, False, 1.5, "USB"),
]

# Conductors that travel through the X chain and through the Y chain (the moving harness)
MOVING = {
    "X chain": ["C3", "C4", "C5", "C6", "C7"],
    "Y chain": ["C5", "C6", "C7"],
}

# --- power --------------------------------------------------------------------------------------------------------
# Assumed currents (typical, to confirm): motor current set on each TMC2209 module, motor supply 24 V.
MOTOR_CURRENT_A = {"X": 1.0, "Y": 1.0, "Z": 1.0, "A": 0.8, "B": 0.8, "P": 0.6}
COIL_RESISTANCE_OHM = 2.0  # assumed, typical NEMA 17 / NEMA 11 range 1.5 to 3
SUPPLY_V = 24.0
SUPPLY_MARGIN = 4.0  # headroom over the holding dissipation for acceleration, losses and the drivers' own supply


def power_budget():
    """Order-of-magnitude sizing. Holding dissipation is two coils at the set current: 2 I^2 R per motor. The supply
    is chosen with a large margin because motion needs far more than holding. A hypothesis, not a measurement."""
    holding = sum(2 * i * i * COIL_RESISTANCE_OHM for i in MOTOR_CURRENT_A.values())
    return holding, holding * SUPPLY_MARGIN


# --- tables -------------------------------------------------------------------------------------------------------
def pin_table():
    rows = []
    for index, axis in enumerate(AXES):
        rows.append((f"{axis} step", PINS["kStepPin"][index], f"TMC2209 {axis} STEP"))
        rows.append((f"{axis} direction", PINS["kDirPin"][index], f"TMC2209 {axis} DIR"))
    rows.append(("Drivers enable (shared, low = on)", PINS["kEnablePin"], "EN of the six TMC2209"))
    for index, axis in enumerate(AXES):
        if PINS["kLimitMinPin"][index] >= 0:
            rows.append((f"{axis} minimum switch", PINS["kLimitMinPin"][index], "NC to ground, pull-up"))
        if PINS["kLimitMaxPin"][index] >= 0:
            rows.append((f"{axis} maximum switch", PINS["kLimitMaxPin"][index], "NC to ground, pull-up"))
    rows.append(("ABORT button", PINS["kAbortPin"], "NC to ground, pull-up"))
    rows.append(("Motor power OK", PINS["kPowerOkPin"], "from an optocoupler, pull-down"))
    rows.append(("Pilot LED", PINS["kLedPin"], "LED with series resistor"))
    rows.append(("Reserved: TMC2209 UART", f"{PINS['kReservedUartTx']} (TX), {PINS['kReservedUartRx']} (RX)", "not used in standalone mode"))
    return rows


def markdown():
    out = ["## Cables\n", "| Id | Cable | Conductors | Shielded | Moves | Length (m) | Connector at the machine end |",
           "|---|---|---|---|---|---|---|"]
    for cid, what, n, shield, moves, length, conn in CABLES:
        out.append(f"| {cid} | {what} | {n} | {'yes' if shield else 'no'} | {'yes' if moves else 'no'} | {length} | {conn} |")
    out.append("\n## Moving harness\n")
    out.append("| Section | Cables | Conductors |\n|---|---|---|")
    counts = {c[0]: c[2] for c in CABLES}
    for section, ids in MOVING.items():
        out.append(f"| {section} | {', '.join(ids)} | {sum(counts[i] for i in ids)} |")
    out.append("\n## Pins\n")
    out.append("| Signal | GPIO | Wiring |\n|---|---|---|")
    for signal, pin, note in pin_table():
        out.append(f"| {signal} | {pin} | {note} |")
    holding, supply = power_budget()
    out.append(f"\n## Motor power (assumed)\n\nMotor currents set on the drivers: {MOTOR_CURRENT_A} A, coil resistance "
               f"{COIL_RESISTANCE_OHM:g} ohm. Holding dissipation about {holding:.0f} W; with a margin of {SUPPLY_MARGIN:g}x, a "
               f"{SUPPLY_V:g} V supply of about {supply:.0f} W ({supply / SUPPLY_V:.1f} A).")
    return "\n".join(out)


# --- checks -------------------------------------------------------------------------------------------------------
def check():
    problems = []
    pins = [v for k, v in PINS.items() if isinstance(v, int) and v >= 0] + [
        p for k, v in PINS.items() if isinstance(v, list) for p in v if p >= 0]
    if len(pins) != len(set(pins)):
        problems.append("a GPIO is used twice")
    ids = [c[0] for c in CABLES]
    if len(ids) != len(set(ids)):
        problems.append("repeated cable id")
    if any(i not in ids for section in MOVING.values() for i in section):
        problems.append("a moving harness lists an unknown cable")
    for cid, _, _, _, moves, length, _ in CABLES:
        if length <= 0:
            problems.append(f"{cid} has no length")
        if any(cid in section for section in MOVING.values()) != moves:
            problems.append(f"{cid} moving flag disagrees with the harness list")
    # every fitted switch pin of the firmware has a cable conductor: X two, Y two, Z one
    fitted = sum(1 for v in PINS["kLimitMinPin"] + PINS["kLimitMaxPin"] if v >= 0)
    if fitted != 5:
        problems.append(f"the firmware fits {fitted} limit switches, the wiring map assumes 5")
    for axis in ("X", "Y", "Z"):
        if PINS["kStepPin"][AXES.index(axis)] < 0:
            problems.append(f"axis {axis} has no step pin")
    return problems


# --- diagram ------------------------------------------------------------------------------------------------------
def diagram(path):
    from PIL import Image, ImageDraw, ImageFont

    w, h = 2000, 1250
    image = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
        bold = ImageFont.truetype("arialbd.ttf", 26)
        small = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = bold = small = ImageFont.load_default()

    def box(x, y, bw, bh, title, lines=(), fill="#eef3fb", outline="#335"):
        draw.rounded_rectangle((x, y, x + bw, y + bh), 14, fill=fill, outline=outline, width=3)
        draw.text((x + 14, y + 10), title, fill="black", font=bold)
        for i, line in enumerate(lines):
            draw.text((x + 14, y + 46 + 26 * i), line, fill="#222", font=small)
        return (x, y, bw, bh)

    def line(a, b, label="", color="#333", width=4, dash=False, dy=0):
        if dash:
            n = 24
            for i in range(0, n, 2):
                p = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
                q = (a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n)
                draw.line((p, q), fill=color, width=width)
        else:
            draw.line((a, b), fill=color, width=width)
        if label:
            draw.text(((a[0] + b[0]) / 2 - 60, (a[1] + b[1]) / 2 - 26 + dy), label, fill=color, font=small)

    draw.text((30, 20), "Wiring map v0.1 (provisional, nothing measured)", fill="black", font=bold)
    # mains and power
    box(30, 110, 330, 150, "Mains (qualified person)", ["Certified enclosure, fuse,", "earth. Not designed here."], "#fdf1e3", "#a60")
    box(30, 330, 330, 150, "24 V supply", [f"about {power_budget()[1]:.0f} W (assumed)", "motors only"], "#fdf1e3", "#a60")
    box(30, 580, 330, 130, "5 V logic supply", ["separate from the motors", "ESP32-S3 and panel"], "#fdf1e3", "#a60")
    # estop chain
    box(470, 330, 330, 150, "E-stop and contactor", ["NC contact opens the", "contactor coil: cuts 24 V", "to the drivers"], "#fdebeb", "#a22")
    # electronics box
    box(920, 110, 520, 560, "Electronics box", ["ESP32-S3  (firmware/board)", "", "6 x TMC2209: X Y Z A B P", "  STEP / DIR per axis, shared EN", "", "Inputs: 5 limit switches (NC),",
                                                 "ABORT (NC), motor power OK", "(optocoupler from the 24 V after", "the contactor)", "", "Connectors on one panel,", "strain relief, label per cable"])
    # machine
    box(1560, 110, 410, 120, "X axis", ["motor C1, switches C2", "static on the crossbeam"])
    box(1560, 260, 410, 120, "Y axis (moves with X)", ["motor C3, switches C4", "through the X chain"])
    box(1560, 410, 410, 120, "Z axis (moves with Y)", ["motor C5, top switch C6", "through the X and Y chains"])
    box(1560, 560, 410, 150, "Tool head (quick change)", ["plunger NEMA 11, wrist A, B: C7", "12 conductors, one connector"])
    # panel and PC
    box(470, 520, 330, 110, "Control panel", ["e-stop, ABORT, pilot: C8", "5 conductors"], "#fdebeb", "#a22")
    box(920, 800, 520, 130, "Host PC", ["USB serial to the ESP32 (C11)", "Python loop, safety heartbeat"])
    box(1560, 800, 410, 130, "Cameras A and B", ["USB to the PC: C9, C10", "no data through the box"])
    # legend
    draw.text((30, 1010), "Red: safety path, independent of PC and firmware.   Orange: power.   Blue: signals.", fill="black", font=font)
    draw.text((30, 1050), "Lengths and counts: see the cable table (python cad/wiring.py). Moving harness: X chain "
              f"{sum(c[2] for c in CABLES if c[0] in MOVING['X chain'])} conductors, Y chain {sum(c[2] for c in CABLES if c[0] in MOVING['Y chain'])}.",
              fill="black", font=font)
    # links
    line((14, 185), (30, 185), "", "#a60")
    line((14, 185), (14, 645), "", "#a60")
    line((14, 645), (30, 645), "", "#a60")
    line((195, 260), (195, 330), "", "#a60")
    line((360, 405), (470, 405), "24 V", "#a60")
    line((800, 405), (920, 405), "24 V to drivers", "#a60", dy=-4)
    line((360, 650), (920, 650), "5 V", "#a60", dy=-4)
    line((635, 480), (635, 520), "", "#a22")
    draw.text((650, 488), "NC chain", fill="#a22", font=small)
    line((800, 575), (920, 575), "C8", "#335")
    line((1440, 170), (1560, 170), "C1 C2", "#335")
    line((1440, 320), (1560, 320), "C3 C4", "#335")
    line((1440, 470), (1560, 470), "C5 C6", "#335")
    line((1440, 635), (1560, 635), "C7", "#335")
    line((1180, 670), (1180, 800), "C11 USB", "#335")
    line((1440, 865), (1560, 865), "C9 C10", "#335")
    image.save(path)


if __name__ == "__main__":
    if "--check" in sys.argv:
        found = check()
        for item in found:
            print("PROBLEM:", item)
        if not found:
            print("WIRING CHECK OK")
        sys.exit(1 if found else 0)
    if "--diagram" in sys.argv:
        diagram(sys.argv[sys.argv.index("--diagram") + 1])
        sys.exit(0)
    print(markdown())
