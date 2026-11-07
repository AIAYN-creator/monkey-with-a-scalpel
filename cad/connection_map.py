"""Connection map: every conductor of every cable, from its pin in the electronics box to its pin at the machine, as a checked netlist.

Usage, from the repository root:
    python cad/connection_map.py                       print the map as Markdown
    python cad/connection_map.py --check               consistency checks (used by the CI), exit code 1 on a problem
    python cad/connection_map.py --markdown FILE       write the Markdown
    python cad/connection_map.py --diagram FILE        draw the cable chart (needs Pillow)

It builds on cad/wiring.py (cables, conductor counts, head board) and on the pins of firmware/board/controller_board/board_config.h, so a
pin that moves in the firmware moves here. The checks are that every GPIO of the firmware appears in exactly one conductor, that no
conductor is used twice, and that each cable has exactly the conductors that wiring.py declares. Provisional, like the rest of the wiring:
typical parts, nothing measured, the mains side and the power cut-off to be built and reviewed by a qualified person.
"""
import sys

import wiring as W

AXES = W.AXES
P = W.PINS
TP = W.TOOL_PINS


def motor(driver, cable, motor_name, first=1):
    """The four coil conductors of a stepper motor from its TMC2209 module."""
    pins = ("M1A", "M1B", "M2A", "M2B")
    labels = ("coil A +", "coil A -", "coil B +", "coil B -")
    return [(cable, first + i, f"{motor_name} {labels[i]}", f"{driver}.{pins[i]}", f"{motor_name}.{labels[i].replace(' ', '')}") for i in range(4)]


def build():
    """Rows (cable, conductor number, signal, pin in the box, pin at the machine)."""
    rows = []
    # motors of the machine axes
    rows += motor("D_X", "C1", "X motor")
    rows += motor("D_Y", "C3", "Y motor")
    rows += motor("D_Z", "C5", "Z motor")
    rows += motor("D_A", "C12", "Wrist A motor")
    rows += motor("D_B", "C13", "Wrist B motor")
    # limit switches: normally closed to ground, internal pull-up, a hit or a broken wire reads high
    rows += [("C2", 1, "X minimum switch", f"U1.GPIO{P['kLimitMinPin'][0]}", "SW_X-.NC"),
             ("C2", 2, "X maximum switch", f"U1.GPIO{P['kLimitMaxPin'][0]}", "SW_X+.NC"),
             ("C2", 3, "switch common ground", "GND_LOGIC", "SW_X-.C and SW_X+.C"),
             ("C4", 1, "Y minimum switch", f"U1.GPIO{P['kLimitMinPin'][1]}", "SW_Y-.NC"),
             ("C4", 2, "Y maximum switch", f"U1.GPIO{P['kLimitMaxPin'][1]}", "SW_Y+.NC"),
             ("C4", 3, "switch common ground", "GND_LOGIC", "SW_Y-.C and SW_Y+.C"),
             ("C6", 1, "Z top switch", f"U1.GPIO{P['kLimitMaxPin'][2]}", "SW_Z+.NC"),
             ("C6", 2, "switch common ground", "GND_LOGIC", "SW_Z+.C")]
    # control panel: dual-contact e-stop and ABORT button, pilot LED
    rows += [("C8", 1, "contactor coil supply to e-stop contact 1", "K1.A1 via ES1.11 loop", "ES1.11"),
             ("C8", 2, "e-stop contact 1 to the contactor coil", "K1.A2 side", "ES1.12"),
             ("C8", 3, "enable loop out (5 V)", "ENABLE_5V", "ES1.21"),
             ("C8", 4, "enable loop return (ES1.22 to AB1.21 in the panel)", "ENABLE_OK", "AB1.22"),
             ("C8", 5, "ABORT button contact 1", f"U1.GPIO{P['kAbortPin']}", "AB1.11"),
             ("C8", 6, "common ground", "GND_LOGIC", "AB1.12 and LED1.K"),
             ("C8", 7, "pilot LED", f"U1.GPIO{P['kLedPin']} via resistor", "LED1.A")]
    # head link: the head board on the Z carriage (see HEAD_BOARD in wiring.py)
    head = [("tool rail 24 V (1)", "K1.TOOL_FUSE", "HB.VIN1"), ("tool rail 24 V (2)", "K1.TOOL_FUSE", "HB.VIN2"),
            ("tool rail ground (1)", "GND_POWER", "HB.GND1"), ("tool rail ground (2)", "GND_POWER", "HB.GND2"),
            ("RS-485 A", "T1.A", "T2.A"), ("RS-485 B", "T1.B", "T2.B"),
            ("enable loop", "ENABLE_OK", "HB.ENABLE"), ("power permit", f"U1.GPIO{TP['tool_power_permit']}", "HB.PERMIT"),
            ("plunger motor A +", "D_P.M1A", "HB.PA1"), ("plunger motor A -", "D_P.M1B", "HB.PA2"),
            ("plunger motor B +", "D_P.M2A", "HB.PB1"), ("plunger motor B -", "D_P.M2B", "HB.PB2")]
    rows += [("C7", i + 1, signal, a, b) for i, (signal, a, b) in enumerate(head)]
    # USB cables
    for cable, what in (("C9", "Camera A"), ("C10", "Camera B"), ("C11", "Host PC")):
        for i, pin in enumerate(("VBUS", "D+", "D-", "GND")):
            far = f"{what}.{pin}" if cable != "C11" else f"U1.USB_{pin}"
            rows.append((cable, i + 1, f"{what} USB {pin}", f"PC.USB_{pin}", far))
    return rows


# Connections that are not a cable: inside the electronics box or on the head board. They are listed so every GPIO is accounted for.
BOX = (
    [(f"U1.GPIO{P['kStepPin'][i]}", f"D_{a}.STEP", f"{a} step") for i, a in enumerate(AXES)]
    + [(f"U1.GPIO{P['kDirPin'][i]}", f"D_{a}.DIR", f"{a} direction") for i, a in enumerate(AXES)]
    + [(f"U1.GPIO{P['kEnablePin']}", "D_X.EN, D_Y.EN, D_Z.EN, D_A.EN, D_B.EN, D_P.EN", "drivers enable (low = on)"),
       (f"U1.GPIO{P['kPowerOkPin']}", "OPTO1.OUT", "motor power OK, after the contactor"),
       (f"U1.GPIO{TP['head_uart_tx']}", "T1.DI", "head link transmit (reclaims the reserved UART TX)"),
       (f"U1.GPIO{TP['head_uart_rx']}", "T1.RO", "head link receive (reclaims the reserved UART RX)")]
)

# Power and safety nets (the box side of the e-stop chain)
POWER = [
    ("PSU24.+", "F1 (fuse) to K1 main contacts 13-14", "24 V from the supply to the contactor"),
    ("K1.14", "D_X.VM, D_Y.VM, D_Z.VM, D_A.VM, D_B.VM, D_P.VM and the tool rail fuse", "24 V after the contactor: motors and tools"),
    ("K1.14 via divider", "OPTO1.IN", "motor power OK sense"),
    ("PSU5.+", "U1.5V, D_*.VIO, T1.VCC, ENABLE_5V source", "5 V logic, separate from the motors"),
    ("ENABLE_5V", "C8.3 to ES1.21, ES1.22 to AB1.21, AB1.22 to C8.4 (ENABLE_OK), then C7.7 to HB.ENABLE", "the enable loop"),
    ("PSU24.+ via ES1.11-12", "K1.A1, K1.A2 to PSU24.-", "the e-stop opens the contactor coil"),
]

# Parts that must be fitted for the map to be true
REQUIREMENTS = [
    "E-stop and ABORT button with two normally closed contacts each (dual contact): contact 1 for the contactor coil and the ABORT pin, contact 2 for the enable loop",
    "RS-485 transceivers with automatic direction control at the controller (T1) and at the head board (T2)",
    "Head board: microcontroller, high-side tool power switch and the discrete AND of the enable loop and the power permit (see wiring.py HEAD_BOARD and HW_CUTOFF_NOTE)",
    "Four changeover relays or analog switches on the head board that route circuits 7-10 either to the plunger motor phases or to the head outputs, selected from the tool identifier; unpowered, the circuits are disconnected from both",
]


def gpios_in_map():
    found = []
    for _cable, _n, _sig, box, _far in build():
        if "U1.GPIO" in box:
            found.append(int(box.split("U1.GPIO")[1].split()[0].rstrip(",")))
    for pin, _to, _what in BOX:
        found.append(int(pin.split("GPIO")[1]))
    return found


def check():
    problems = []
    rows = build()
    declared = {c[0]: c[2] for c in W.CABLES}
    counts = {}
    for cable, number, *_rest in rows:
        counts[cable] = counts.get(cable, 0) + 1
    for cable, n in declared.items():
        if counts.get(cable, 0) != n:
            problems.append(f"{cable} has {counts.get(cable, 0)} conductors in the map and {n} in wiring.py")
    for cable in counts:
        if cable not in declared:
            problems.append(f"the map has conductors on {cable}, which wiring.py does not declare")
    seen = set()
    for cable, number, *_rest in rows:
        if (cable, number) in seen:
            problems.append(f"{cable} conductor {number} appears twice")
        seen.add((cable, number))
    used = gpios_in_map()
    if len(used) != len(set(used)):
        problems.append("a GPIO appears in more than one connection")
    firmware = {p for k, v in P.items() if isinstance(v, int) and v >= 0 and k not in ("kReservedUartTx", "kReservedUartRx") for p in [v]}
    firmware |= {p for v in P.values() if isinstance(v, list) for p in v if p >= 0}
    firmware |= set(TP.values())
    if set(used) != firmware:
        problems.append(f"GPIOs in the firmware and not in the map: {sorted(firmware - set(used))}; in the map and not in the firmware: {sorted(set(used) - firmware)}")
    if sum(n for _w, n in W.HEAD_LINK) != counts.get("C7"):
        problems.append("the head link of wiring.py and the C7 conductors of the map differ")
    return problems


def markdown():
    intro = ("Every conductor from its pin in the electronics box to its pin at the machine. Pins of the controller come from "
             "`board_config.h`; cables, lengths and conductor counts from `cad/wiring.py`. Nothing here is measured or verified.\n")
    out = ["# Connection map (generated by `python cad/connection_map.py`; provisional)\n", intro]
    lengths = {c[0]: c[5] for c in W.CABLES}
    names = {c[0]: c[1] for c in W.CABLES}
    cables = []
    for cable, *_ in build():
        if cable not in cables:
            cables.append(cable)
    for cable in cables:
        out.append(f"## {cable}: {names[cable]} ({lengths[cable]} m)\n")
        out.append("| # | Signal | Box end | Machine end |\n|---|---|---|---|")
        for c, n, signal, box, far in build():
            if c == cable:
                out.append(f"| {n} | {signal} | {box} | {far} |")
        out.append("")
    out.append("## Inside the electronics box\n\n| Controller pin | Goes to | Function |\n|---|---|---|")
    for pin, to, what in BOX:
        out.append(f"| {pin} | {to} | {what} |")
    out.append("\n## Power and safety nets\n\n| From | To | What |\n|---|---|---|")
    for a, b, what in POWER:
        out.append(f"| {a} | {b} | {what} |")
    out.append("\n## Tool connector (12 circuits) on the head board, by tool\n")
    out.append("Circuits 1-2 switched 24 V, 3-4 ground, 5 logic 5 V, 6 identification (1-wire). Circuits 7-12 by tool:\n")
    out.append("| Tool | Circuit: signal (kind) |\n|---|---|")
    for name, wiring in W.TOOL_WIRING.items():
        out.append(f"| {name} | " + "; ".join(f"{c}: {s} ({k})" for c, (s, k) in sorted(wiring.items())) + " |")
    out.append("\n## Parts that must be fitted\n")
    out += [f"- {r}" for r in REQUIREMENTS]
    return "\n".join(out) + "\n"


FUNCTION_COLOR = [("coil", "#d9801e"), ("RS-485", "#3a6fb0"), ("USB", "#6b7b8c"), ("switch", "#2e8b57"), ("ground", "#444444"),
                  ("tool rail", "#c0392b"), ("enable", "#b8860b"), ("permit", "#b8860b"), ("plunger", "#d9801e"), ("ABORT", "#a22"),
                  ("contactor", "#a22"), ("e-stop", "#a22"), ("LED", "#2e8b57")]


def color_of(signal):
    for key, color in FUNCTION_COLOR:
        if key.lower() in signal.lower():
            return color
    return "#335"


def diagram(path):
    from PIL import Image, ImageDraw, ImageFont

    rows = build()
    cables = []
    for cable, *_ in rows:
        if cable not in cables:
            cables.append(cable)
    try:
        font, bold = ImageFont.truetype("arial.ttf", 17), ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        font = bold = ImageFont.load_default()
    names = {c[0]: c[1] for c in W.CABLES}
    lengths = {c[0]: c[5] for c in W.CABLES}
    line_h, gap, width = 24, 22, 2400
    height = 90 + sum(60 + line_h * sum(1 for r in rows if r[0] == c) + gap for c in cables) + 60
    image = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(image)
    d.text((30, 20), "Vernier: connection map (provisional, nothing measured). Box end on the left, machine end on the right.", fill="black", font=bold)
    y = 70
    for cable in cables:
        mine = [r for r in rows if r[0] == cable]
        h = 40 + line_h * len(mine)
        d.rounded_rectangle((20, y, width - 20, y + h), 10, fill="#f6f8fb", outline="#335", width=2)
        d.text((36, y + 8), f"{cable}  {names[cable]}  -  {lengths[cable]} m", fill="black", font=bold)
        for i, (_c, n, signal, box, far) in enumerate(mine):
            yy = y + 38 + line_h * i
            col = color_of(signal)
            d.text((40, yy), f"{n:>2}", fill="black", font=font)
            d.text((80, yy), box[:46], fill="#222", font=font)
            d.line((620, yy + 10, 780, yy + 10), fill=col, width=5)
            d.text((800, yy), signal[:62], fill=col, font=font)
            d.line((1480, yy + 10, 1640, yy + 10), fill=col, width=5)
            d.text((1660, yy), far[:46], fill="#222", font=font)
        y += h + gap
    image.save(path)


if __name__ == "__main__":
    if "--check" in sys.argv:
        found = check()
        for item in found:
            print("PROBLEM:", item)
        if not found:
            print("CONNECTION MAP OK")
        sys.exit(1 if found else 0)
    if "--markdown" in sys.argv:
        from pathlib import Path

        Path(sys.argv[sys.argv.index("--markdown") + 1]).write_text(markdown(), encoding="utf-8")
        sys.exit(0)
    if "--diagram" in sys.argv:
        diagram(sys.argv[sys.argv.index("--diagram") + 1])
        sys.exit(0)
    print(markdown())
