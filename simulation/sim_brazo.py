"""Phase 0 base simulation (card p0-02): XYZ gantry, optional wrist and a fixed target.

Architecture from dec-arq: an XYZ gantry moves the tool, a wrist of 0-2 axes sets the
approach angle, and the sample stays fixed. The model works in metres and radians; the
distance to the target is reported in millimetres.

Usage:
    python sim_brazo.py                  print the tip-to-target distance in mm
    python sim_brazo.py --wrist-dof 1    use a one-axis wrist (0, 1 or 2)
    python sim_brazo.py --save-xml m.xml write the model so it can be opened in the viewer
    python sim_brazo.py --check          run the geometry self-check
"""
import argparse
import sys

import mujoco
import numpy as np

# Geometry, in metres.
GANTRY_HEIGHT = 0.15  # height of the Z carriage above the table at the zero pose
TOOL_LENGTH = 0.13  # from the wrist pivot to the needle tip
STROKE = 0.05  # half travel of each linear axis (100 mm useful travel in total)
WRIST_RANGE = 0.8  # half range of each wrist axis, radians
TARGET_POS = (0.04, -0.03, 0.01)
TARGET_RADIUS = 0.004

LINEAR_JOINTS = ("x", "y", "z")
WRIST_JOINTS = ("tilt_y", "tilt_x")  # inclination about Y, then about X


def build_xml(wrist_dof=2):
    """Return the MJCF of the gantry with `wrist_dof` wrist axes (0, 1 or 2)."""
    if wrist_dof not in (0, 1, 2):
        raise ValueError("wrist_dof must be 0, 1 or 2")
    needle_start = TOOL_LENGTH * 0.6
    tool = f"""
        <geom name="syringe" type="capsule" fromto="0 0 0 0 0 {-needle_start}"
              size="0.006" rgba="0.75 0.85 0.95 1"/>
        <geom name="needle" type="capsule" fromto="0 0 {-needle_start} 0 0 {-TOOL_LENGTH}"
              size="0.0012" rgba="0.3 0.3 0.3 1"/>
        <site name="tip" pos="0 0 {-TOOL_LENGTH}" size="0.002" rgba="1 1 0 1"/>"""
    # Wrist axes nest around the tool: tilt about Y outside, tilt about X inside.
    if wrist_dof >= 2:
        tool = f"""
        <body name="wrist_x">
          <joint name="tilt_x" type="hinge" axis="1 0 0" range="{-WRIST_RANGE} {WRIST_RANGE}"/>
          <geom type="sphere" size="0.007" rgba="0.8 0.3 0.3 1"/>{tool}
        </body>"""
    if wrist_dof >= 1:
        tool = f"""
      <body name="wrist_y">
        <joint name="tilt_y" type="hinge" axis="0 1 0" range="{-WRIST_RANGE} {WRIST_RANGE}"/>
        <geom type="sphere" size="0.008" rgba="0.8 0.3 0.3 1"/>{tool}
      </body>"""
    return f"""
<mujoco model="gantry_wrist">
  <compiler angle="radian"/>
  <option gravity="0 0 0"/>
  <default>
    <geom contype="0" conaffinity="0"/>
  </default>
  <worldbody>
    <light pos="0 0 1" dir="0 0 -1"/>
    <geom name="table" type="plane" size="0.25 0.25 0.01" rgba="0.85 0.85 0.85 1"/>
    <geom name="frame_left" type="box" pos="-0.2 0 0.1" size="0.01 0.2 0.1" rgba="0.5 0.5 0.55 1"/>
    <geom name="frame_right" type="box" pos="0.2 0 0.1" size="0.01 0.2 0.1" rgba="0.5 0.5 0.55 1"/>
    <site name="target" pos="{TARGET_POS[0]} {TARGET_POS[1]} {TARGET_POS[2]}"
          size="{TARGET_RADIUS}" rgba="1 0 0 1"/>
    <camera name="top" pos="0 -0.45 0.35" xyaxes="1 0 0 0 0.6 0.8"/>
    <body name="x_carriage" pos="0 0 {GANTRY_HEIGHT}">
      <joint name="x" type="slide" axis="1 0 0" range="{-STROKE} {STROKE}"/>
      <geom type="box" size="0.02 0.02 0.01" rgba="0.2 0.5 0.8 1"/>
      <body name="y_carriage">
        <joint name="y" type="slide" axis="0 1 0" range="{-STROKE} {STROKE}"/>
        <geom type="box" size="0.015 0.015 0.012" rgba="0.2 0.7 0.5 1"/>
        <body name="z_carriage">
          <joint name="z" type="slide" axis="0 0 1" range="{-STROKE} {STROKE}"/>
          <geom type="box" size="0.01 0.01 0.014" rgba="0.9 0.6 0.2 1"/>{tool}
        </body>
      </body>
    </body>
  </worldbody>
</mujoco>
"""


def build_model(wrist_dof=2):
    """Compile the model and return (model, data) at the zero pose."""
    model = mujoco.MjModel.from_xml_string(build_xml(wrist_dof))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


def _joint_index(model, name):
    """Index of a joint in qpos, or None if the model has no such joint."""
    try:
        return model.joint(name).qposadr[0]
    except KeyError:
        return None


def set_pose(model, data, x=0.0, y=0.0, z=0.0, tilt_y=0.0, tilt_x=0.0):
    """Set the gantry (m) and wrist (rad) coordinates. Wrist axes missing from the model are ignored."""
    values = {"x": x, "y": y, "z": z, "tilt_y": tilt_y, "tilt_x": tilt_x}
    for name, value in values.items():
        index = _joint_index(model, name)
        if index is not None:
            data.qpos[index] = value
    mujoco.mj_forward(model, data)


def calcular_distancia(model, data):
    """Distance between the needle tip and the target, in millimetres."""
    tip = data.site("tip").xpos
    target = data.site("target").xpos
    return float(np.linalg.norm(tip - target) * 1000.0)


def self_check():
    """Compare the model against hand-computed geometry. Raises AssertionError on a mismatch."""
    model, data = build_model(wrist_dof=2)
    zero_tip = np.array([0.0, 0.0, GANTRY_HEIGHT - TOOL_LENGTH])
    assert np.allclose(data.site("tip").xpos, zero_tip, atol=1e-9), "zero-pose tip is wrong"

    set_pose(model, data, x=0.01)
    assert np.allclose(data.site("tip").xpos, zero_tip + [0.01, 0.0, 0.0], atol=1e-9), "X axis is wrong"

    set_pose(model, data, tilt_y=np.pi / 2)
    expected = np.array([-TOOL_LENGTH, 0.0, GANTRY_HEIGHT])
    assert np.allclose(data.site("tip").xpos, expected, atol=1e-9), "wrist tilt about Y is wrong"

    on_target = np.array(TARGET_POS) - zero_tip
    set_pose(model, data, x=on_target[0], y=on_target[1], z=on_target[2])
    assert calcular_distancia(model, data) < 1e-6, "tip placed on the target should give distance 0"

    set_pose(model, data)
    manual = np.linalg.norm(zero_tip - np.array(TARGET_POS)) * 1000.0
    assert abs(calcular_distancia(model, data) - manual) < 1e-9, "distance does not match the manual value"

    fixed_model, _ = build_model(wrist_dof=0)
    assert _joint_index(fixed_model, "tilt_y") is None, "a model without wrist should have no wrist joints"
    print("SELF-CHECK OK")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wrist-dof", type=int, default=2, choices=(0, 1, 2))
    parser.add_argument("--save-xml", metavar="PATH")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if args.check:
        self_check()
        return 0
    if args.save_xml:
        with open(args.save_xml, "w", encoding="utf-8") as f:
            f.write(build_xml(args.wrist_dof))
        print(f"model written to {args.save_xml}", file=sys.stderr)

    model, data = build_model(args.wrist_dof)
    print(f"zero pose, wrist axes: {args.wrist_dof}; distance in mm:", file=sys.stderr)
    print(f"{calcular_distancia(model, data):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
