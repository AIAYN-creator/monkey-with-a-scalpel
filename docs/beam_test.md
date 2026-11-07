# Test beam (card mech-viga)

The hollow printed crossbeam with four aluminium rods is a hand calculation. Its bending stiffness is dominated by the rods; what is
unknown is the **bond** (epoxy between rods and bores) and the **shell** (printed PETG, assumed 1.8 GPa and shear 0.65 GPa). This
400 mm beam measures both before anything bigger is printed. **Nothing here has been printed or measured yet.**

## Build

```
python cad/test_beam.py out --section 60x80      # or 80x100
```

Print 2 segments and 2 end plates (PETG, 3 perimeters, 40 % gyroid or more; the walls are 3 mm). Buy 4 rods of 8 mm x 412 mm. Bond the rods
with epoxy through the bores of both segments, with the end plates on, and let it cure 24 h. Make a second beam without epoxy as a control
(the difference is the value of the bond). The script prints the predicted sag and twist for each section.

## Test 1: bending

Two supports 380 mm apart (the beam rests on rounded steel bars), a 1 um dial indicator under the middle, hang 20 kg from the middle in 5
steps and back. Read the sag at each step. Expect the prediction within 1.5x and no visible hysteresis; a larger sag means the bond slips
or the segments open at the joint.

## Test 2: torsion

Clamp one end plate to the bench with the beam level, bolt a 300 mm arm to the free end plate, hang 30 N at its end, read the arm
displacement with the dial indicator (twist = displacement / 300). This is the number that decides the section: the model gives about 0.37
deg for 60x80 and 0.17 deg for 80x100. Repeat three times and after 24 h under load for creep (PETG creeps; the real beam carries a
constant load).

## What the result changes

| Result | Decision |
|---|---|
| Both within 1.5x of the prediction, creep under 10 % | keep the section; design the rail seat and the rod retention |
| Twist larger than predicted | go to 80x100 mm, or add a diagonal strut or a counterweight for the Y cantilever |
| Sag larger than predicted, or hysteresis | the bond or the joint is the weak point: add spigots at the joints, or glue length and surface |
| Creep large | change the material (PETG-CF, nylon-CF) or fill the shell with epoxy |

Record the numbers in the card `mech-viga`; do not edit the assumptions in `cad/mech_review.py` until a measurement replaces them.
