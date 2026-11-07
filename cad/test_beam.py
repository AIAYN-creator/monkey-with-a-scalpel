"""Test beam for card mech-viga: two printed segments and four aluminium rods, 400 mm, plus what to expect when you load it.

Usage, from the repository root (needs build123d):
    python cad/test_beam.py OUT_DIR [--section 60x80|80x100]

It exports the STL files of the segment and the two end plates (print 2 segments and 2 plates per beam) and prints the deflection
and the twist the model predicts for the two tests in docs/beam_test.md, so the measurement can be compared with the number. The
prediction uses the same assumptions as `cad/mech_review.py` (PETG 1.8 GPa, shear 0.65 GPa, aluminium 70 GPa); the test exists to
check them, so a result far from the prediction is the finding, not a failure of the test.
"""
import math
import sys
from pathlib import Path

import modules.beam as B
import params as P
from build123d import export_stl

E_AL, E_PETG, G_PETG = 70e3, 1.8e3, 0.65e3  # MPa
LENGTH = 2 * B.SEG_MAX  # mm, the beam under test
SPAN = LENGTH - 20.0  # mm between the two supports of the bending test
BEND_LOAD = 200.0  # N at mid span (20 kg hung from the middle); the sag is only tens of um, read it with a 1 um dial indicator
TORSION_ARM, TORSION_LOAD = 300.0, 30.0  # mm, N: a weight hung from an arm bolted to the free end


def prediction(w, h):
    wall, rod_d = B.WALL, B.ROD_D
    off_z = h / 2 - wall - B.BORE_D / 2
    off_y = w / 2 - wall - B.BORE_D / 2
    i_rods = 4 * (math.pi * rod_d ** 2 / 4 * off_z ** 2 + math.pi * rod_d ** 4 / 64)
    i_shell = (w * h ** 3 - (w - 2 * wall) * (h - 2 * wall) ** 3) / 12
    ei = E_AL * i_rods + E_PETG * i_shell  # N mm2
    sag = BEND_LOAD * SPAN ** 3 / (48 * ei)
    a_m, perim = (w - wall) * (h - wall), 2 * ((w - wall) + (h - wall))
    j = 4 * a_m ** 2 * wall / perim
    torque = TORSION_LOAD * TORSION_ARM  # N mm
    twist = torque * LENGTH / (G_PETG * j)
    return ei, sag, twist, off_y, off_z


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    section = "60x80"
    if "--section" in sys.argv:
        section = sys.argv[sys.argv.index("--section") + 1]
        args = [a for a in args if a != section]
    w, h = (float(v) for v in section.split("x"))
    P.BEAM_W, P.BEAM_H = w, h
    out = Path(args[0]) if args else Path("test_beam_out")
    out.mkdir(parents=True, exist_ok=True)
    export_stl(B.beam_segment(B.SEG_MAX), str(out / f"test_beam_segment_{section}.stl"))
    export_stl(B.beam_end_plate(), str(out / f"test_beam_end_plate_{section}.stl"))
    ei, sag, twist, _, _ = prediction(w, h)
    print(f"Test beam {section} mm, {LENGTH:.0f} mm long: print 2 segments + 2 plates, buy 4 rods of 8 mm x {LENGTH + 2 * B.END_T:.0f} mm")
    print(f"  bending stiffness EI predicted: {ei / 1e9:.2f} kN m2")
    print(f"  test 1, {BEND_LOAD:g} N at mid span over {SPAN:.0f} mm: sag {sag * 1000:.0f} um")
    print(f"  test 2, {TORSION_LOAD:g} N on a {TORSION_ARM:g} mm arm: twist {math.degrees(twist):.3f} deg "
          f"({twist * TORSION_ARM * 1000:.0f} um at the arm end)")
    print("  reading: measured sag or twist above 1.5x the prediction means the bond or the shell is weaker than assumed")


if __name__ == "__main__":
    main()
