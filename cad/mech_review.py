"""First-pass mechanical review of the provisional design, by hand calculation (numpy only, no FEA).

Usage, from the repository root:
    python cad/mech_review.py

Every input is an assumption or a typical value (marked). The results are orders of magnitude to decide where
to look first and what to simulate with FEA; they are NOT a verification. Closed-loop control with the camera
corrects static deflections, so what matters most is that the deflection is repeatable, that the structure
settles quickly (natural frequency) and that nothing creeps or drops when the power is off.
"""
import math

import params as P

G = 9.81
E_AL, E_STEEL = 70e3, 200e3  # MPa, typical
ASSUMED = []


def assume(label, value, unit, note=""):
    ASSUMED.append((label, value, unit, note))
    return value


# --- masses (kg), from CAD volumes at 50 % infill for printed parts, typical for the purchased ones -------------
FILL = assume("print infill, mass fraction of the solid", 0.5, "-", "assumed")
PETG, AL = 1.27, 2.70  # g/cm3
m_tool_printed = sum(v * PETG * FILL for v in (11.78, 36.78, 11.80, 4.46)) / 1000  # clamp, backplate, mount, coupler
m_actuator = assume("NEMA 11 captive actuator", 0.15, "kg", "typical")
m_syringe = assume("Hamilton 10 uL with plunger", 0.01, "kg", "assumed")
m_tool = m_tool_printed + m_actuator + m_syringe
m_zcar = assume("Z carriage + printed carriage plate", round(0.04 + 28.86 * PETG * FILL / 1000, 3), "kg", "typical + CAD")
m_zplate = 73.89 * AL / 1000 * (200.0 + P.DZ) / 200.0  # the plate is 200 mm at 100 mm of Z travel
m_riser = 84.38 * AL / 1000
m_zmotor = assume("NEMA 17 (40 mm)", 0.28, "kg", "typical")
m_zscrew_knob = assume("Z screw + knob + rail", round(0.18 + 0.0012 * P.DZ, 3), "kg", "assumed, 1.2 g per mm of Z travel")
m_on_ycar = m_tool + m_zcar + m_zplate + m_riser + m_zmotor + m_zscrew_knob
m_yplate = 73.89 * AL / 1000 * (200.0 + P.DY) / 200.0  # same plate, as long as the Y travel needs
m_ydrive = assume("Y motor + screw + rail", round(0.5 + 0.0025 * P.DY, 3), "kg", "assumed, 2.5 g per mm of Y travel for the rail and screw")
m_on_xcar = m_on_ycar + m_yplate + m_ydrive


def report():
    rows = []

    def row(item, value, unit, note=""):
        rows.append((item, value, unit, note))

    row("Mass of the tool head", round(m_tool, 3), "kg")
    row("Mass carried by the Y carriage", round(m_on_ycar, 2), "kg", "tool, Z stage, riser, Z motor")
    row("Mass carried by the X carriage", round(m_on_xcar, 2), "kg", "plus Y plate and Y drive")

    # moments on the carriages (static, worst position)
    arm = P.ARM_REACH + 3 + 6 + P.CARR_H + 26.0  # from the Y carriage centre to the tool axis, mm
    cg_arm = arm * 0.6  # centre of mass of the Z stage is between the riser leg and the tool axis
    m_y = m_on_ycar * G * cg_arm / 1000
    row("Pitch moment on the Y carriage (centre of mass 0.6 of the reach)", round(m_y, 2), "N m",
        "compare with the carriage rating in the datasheet")
    yoff = P.TRAVEL_Y / 2 + 0.0
    m_x = m_on_xcar * G * (cg_arm * 0.9) / 1000
    row("Pitch moment on the X carriage", round(m_x, 2), "N m", "compare with the carriage rating in the datasheet")
    row("Extra moment on the X carriage at full Y travel", round(m_on_ycar * G * yoff / 1000, 2), "N m")

    # Z plate: aluminium 6 mm cantilevered from the riser pattern, tool in front
    b = 62.0
    for t in (6.0, 10.0, 12.0):
        inertia = b * t ** 3 / 12
        for zc, label in ((P.TIP_MIN + 30 + 93, "carriage low"), (P.TIP_MIN + 30 + 93 + P.TRAVEL, "carriage high")):
            l = (265.0 + P.DZ) - zc  # from the pattern to the carriage
            f = (m_tool + m_zcar) * G
            c = 45.0  # lever of the tool centre of mass in front of the plate, mm
            m = f * c
            defl = f * l ** 3 / (3 * E_AL * inertia) + m * l ** 2 / (2 * E_AL * inertia)
            tilt = f * l ** 2 / (2 * E_AL * inertia) + m * l / (E_AL * inertia)
            tip = tilt * ((265.0 + P.DZ) - P.TIP_MIN)
            row(f"Z plate {t:g} mm, {label}: tilt at the carriage", round(math.degrees(tilt), 3), "deg",
                f"tip shift about {tip * 1000:.0f} um, deflection {defl * 1000:.0f} um")
        k = 3 * E_AL * inertia / ((265.0 + P.DZ) - (P.TIP_MIN + 30 + 93 + P.TRAVEL / 2)) ** 3 * 1000  # N/m
        freq = math.sqrt(k / (m_tool + m_zcar)) / (2 * math.pi)
        row(f"Z plate {t:g} mm: first mode (tool on a cantilever, mid travel)", round(freq), "Hz",
            "aim for 50 Hz or more")

    # Z plate printed instead of machined: same load case, carriage low. Moduli are assumptions (printed parts are
    # anisotropic and creep); a T section (flange 62 x 6 plus a central rib) keeps the 6 mm face and adds depth.
    e_petg = assume("PETG modulus along the layers", 1.8e3, "MPa", "typical range 1.5 to 2.1 GPa; across layers it is lower")
    e_cf = assume("carbon-fibre filled nylon or ASA modulus along the layers", 4.0e3, "MPa", "vendor values vary a lot: verify")

    def t_section(rib_w, rib_h, flange_w=62.0, flange_t=6.0):
        a1, a2 = flange_w * flange_t, rib_w * rib_h
        y1, y2 = flange_t / 2, flange_t + rib_h / 2
        yc = (a1 * y1 + a2 * y2) / (a1 + a2)
        return (flange_w * flange_t ** 3 / 12 + a1 * (y1 - yc) ** 2 + rib_w * rib_h ** 3 / 12 + a2 * (y2 - yc) ** 2)

    zc = P.TIP_MIN + 30 + 93
    l = (265.0 + P.DZ) - zc
    f = (m_tool + m_zcar) * G
    for label, e_mod, inertia in (
        ("aluminium 6 mm (reference)", E_AL, 62.0 * 6 ** 3 / 12),
        ("PETG solid 20 mm", e_petg, 62.0 * 20 ** 3 / 12),
        ("PETG, 6 mm face + central rib 10 x 16", e_petg, t_section(10.0, 16.0)),
        ("carbon-fibre filled, 6 mm face + central rib 10 x 16", e_cf, t_section(10.0, 16.0)),
        ("carbon-fibre filled, solid 12 mm", e_cf, 62.0 * 12 ** 3 / 12),
    ):
        tilt = f * l ** 2 / (2 * e_mod * inertia) + f * 45.0 * l / (e_mod * inertia)
        row(f"Z plate, {label}: tilt at the carriage (carriage low)", round(math.degrees(tilt), 3), "deg",
            f"tip shift about {tilt * ((265.0 + P.DZ) - P.TIP_MIN) * 1000:.0f} um; E I = {e_mod * inertia / 1e6:.1f} N m2")

    # crossbeam: 2020 profile
    ix = assume("2020 profile second moment of area", 1.0e4, "mm4", "order of magnitude, verify the datasheet")
    j = assume("2020 profile torsion constant", 1.0e4, "mm4", "order of magnitude, verify the datasheet")
    span = 2 * (P.UPRIGHT_X - P.PROFILE / 2)
    w = m_on_xcar * G
    sag = w * span ** 3 / (48 * E_AL * ix)
    row("Crossbeam sag at the centre under the stack (2020 profile, for comparison)", round(sag * 1000), "um", "simply supported 2020, assumed I")
    torque = w * (P.ARM_REACH * 0.8) / 1000  # N m
    gj = 26e3 * j
    twist = torque * 1000 * (span / 4) / gj
    row("Crossbeam torque from the cantilevered stack", round(torque, 2), "N m")
    row("Crossbeam twist at mid span (2020 profile, for comparison)", round(math.degrees(twist), 3), "deg",
        f"tip shift about {twist * 317 * 1000:.0f} um (lever 317 mm), assumed J")

    # crossbeam as a hollow printed box with four aluminium rods (card mech-viga)
    g_petg = assume("PETG shear modulus", 0.65e3, "MPa", "about E / 2.7; verify with a printed test beam")
    for bw, bh in ((40.0, 60.0), (60.0, 80.0), (80.0, 100.0)):
        wall, rod_d = 3.0, 8.0
        off_z = bh / 2 - wall - rod_d / 2 - 0.2
        i_rods = 4 * (math.pi * rod_d ** 2 / 4 * off_z ** 2 + math.pi * rod_d ** 4 / 64)
        i_shell = (bw * bh ** 3 - (bw - 2 * wall) * (bh - 2 * wall) ** 3) / 12
        ei = E_AL * i_rods + e_petg * i_shell  # N mm2
        sag_p = w * span ** 3 / (48 * ei)
        a_m, perim = (bw - wall) * (bh - wall), 2 * ((bw - wall) + (bh - wall))
        j_p = 4 * a_m ** 2 * wall / perim
        twist_p = torque * 1000 * (span / 4) / (g_petg * j_p)
        row(f"Printed hollow beam {bw:g} x {bh:g} mm, four 8 mm rods: bending stiffness", round(ei / 1e9, 2), "kN m2",
            f"sag {sag_p * 1000:.0f} um at the centre; the 2020 profile is {E_AL * ix / 1e9:.2f}")
        row(f"Printed hollow beam {bw:g} x {bh:g} mm: twist at mid span", round(math.degrees(twist_p), 3), "deg",
            f"tip shift about {twist_p * 317 * 1000:.0f} um (lever 317 mm); the shell carries the torsion, the rods do not")

    # uprights: sway
    h = P.CROSSBEAM_TOP
    k = 2 * 3 * E_AL * ix / h ** 3 * 1000
    freq = math.sqrt(k / (m_on_xcar + 1.0)) / (2 * math.pi)
    row("Frame sway mode, uprights perfectly clamped (upper bound)", round(freq), "Hz",
        "real joints are much softer: add gussets or diagonal braces")

    # Z lead screw
    lead, d_pitch, d_root = 2.0, 7.0, 6.2
    lam = math.atan(lead / (math.pi * d_pitch))
    mu_lock = math.tan(lam) * math.cos(math.radians(14.5))
    row("T8x2 self-locking needs a friction coefficient above", round(mu_lock, 3), "-",
        "POM nut on steel is about 0.1 to 0.2: marginal; add a brake or a friction nut, vibration can back-drive")
    for axis, length in (("X", 210.0 + P.DX), ("Y", 190.0 + P.DY), ("Z", 240.0 + P.DZ)):
        crit = 1.0 * d_root / length ** 2 * 1e7
        row(f"{axis} screw critical speed (floating end, length {length:.0f} mm)", round(crit), "rpm",
            f"keep below 80 %: {0.8 * crit * lead / 60:.0f} mm/s; the machine feed is up to 20 mm/s")
    ecr = math.pi ** 2 * E_STEEL * (math.pi * d_root ** 4 / 64) / length ** 2
    row("Z screw buckling load", round(ecr), "N", "far above the load")
    force = (m_tool + m_zcar) * G
    torque_motor = force * lead / (2 * math.pi * 0.3) / 1000
    row("Torque to lift the tool (efficiency 0.3)", round(torque_motor, 3), "N m", "a NEMA 17 gives about 0.4 N m")

    # --- stiffening (card mech-z): box crossbeam and braced uprights; every value below rests on the marked assumptions ---
    t_wall = assume("effective wall of the box section (two profiles joined by plates)", 2.0, "mm", "assumed; the real joint stiffness decides")
    b_box, h_box = P.PROFILE - t_wall, 2 * P.PROFILE - t_wall
    j_box = 4 * (b_box * h_box) ** 2 * t_wall / (2 * (b_box + h_box))  # Bredt-Batho, thin-walled closed section
    twist_box = torque * 1000 * (span / 4) / (26e3 * j_box)
    row("Crossbeam as a box (two profiles joined): torsion constant", round(j_box), "mm4",
        f"{j_box / j:.1f} times the single profile; assumed wall")
    row("Crossbeam twist at mid span, box", round(math.degrees(twist_box), 3), "deg",
        f"tip shift about {twist_box * 317 * 1000:.0f} um (single profile: {twist * 317 * 1000:.0f} um)")
    area_brace = assume("2020 profile cross-section area", 360.0, "mm2", "typical, verify the datasheet")
    k_joint = assume("stiffness of a printed brace bracket along the brace", 3000.0, "N/mm", "assumed; measure it")
    brace_dy, brace_dz = 120.0, 170.0  # from cad/modules/bracing.py
    brace_len = math.hypot(brace_dy, brace_dz)
    k_axial = E_AL * area_brace / brace_len
    k_brace = 1 / (1 / k_axial + 2 / k_joint)  # a brace in series with its two brackets
    k_sway = 2 * k_brace * (brace_dy / brace_len) ** 2 * 1000  # N/m, two braces working in the direction of the load
    f_sway = math.sqrt(k_sway / (m_on_xcar + 1.0)) / (2 * math.pi)
    row("Frame sway mode with the diagonal braces and printed brackets", round(f_sway), "Hz",
        "dominated by the brackets; only as good as the assumed bracket stiffness")

    # --- Z axis back-drive with the power off (card mech-z) ---
    r_m = d_pitch / 2
    detent = assume("unpowered NEMA 17 detent torque", 10.0, "N mm", "typical 1 to 2.5 N cm, confirm in the datasheet")
    for mu in (0.03, 0.05, 0.15):
        phi = math.atan(mu / math.cos(math.radians(14.5)))
        load_torque = max(0.0, force * r_m * math.tan(lam - phi))  # torque the load puts on the motor, N mm
        row(f"Torque the Z load puts on the motor at friction {mu}", round(load_torque, 2), "N mm",
            f"detent torque {detent:g} N mm: margin {detent / load_torque:.0f}x" if load_torque > 0 else "self-locking: no torque")
    return rows


if __name__ == "__main__":
    print("| Item | Value | Unit | Note |\n|---|---|---|---|")
    for item, value, unit, note in report():
        print(f"| {item} | {value} | {unit} | {note} |")
    print("\nAssumed inputs:")
    for label, value, unit, note in ASSUMED:
        print(f"- {label}: {value} {unit} ({note})")
