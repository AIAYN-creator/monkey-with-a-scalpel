"""Phase 0 self-correction loop (card p0-03).

Starting from a pose far from the target, the loop repeats: measure the tip-to-target error,
compute a correction, move the axes, and measure again, until the distance is below the
tolerance or the iteration limit is reached. Every iteration is logged to a CSV.

The correction is a damped least-squares step on the position Jacobian of the tip, scaled by a
gain below 1 so the approach is gradual, and capped per iteration so the tool never jumps.
By default only the gantry axes move; the wrist stays at its starting angle, which models an
approach with a fixed entry angle. Pass --wrist-active to let the wrist axes correct too.

The measurement and the actuation are plain functions passed to `autocorrect`, so that later
cards can replace them with versions that add camera noise (measure) or backlash (actuate).

Usage, from the repository root:
    python simulation/loop_autocorreccion.py
    python simulation/loop_autocorreccion.py --wrist-active --out logs/other.csv
"""
import argparse
import csv
import sys
from pathlib import Path

import mujoco
import numpy as np
import sim_brazo

TOLERANCE_MM = 0.01  # stop when the tip is closer than this to the target
MAX_ITERATIONS = 50  # corrections allowed after the starting measurement
GAIN = 0.3  # fraction of the error corrected per iteration
DAMPING = 1e-6  # regularises the least-squares solve
MAX_TIP_STEP_M = 0.02  # largest tip displacement allowed in one iteration
MIN_ROWS = 10  # the log must show a gradual approach, not a single jump

# Far from the target, with the wrist tilted: the wrist keeps this angle unless --wrist-active.
START_POSE = {"x": -0.08, "y": 0.07, "z": 0.09, "tilt_y": 0.3, "tilt_x": -0.2}

CSV_COLUMNS = ("iteration", "x_mm", "y_mm", "z_mm", "tilt_y_rad", "tilt_x_rad", "distance_mm", "tip_step_mm")


def measure_error(model, data):
    """Error vector from the tip to the target, in metres. This is what the cameras will provide."""
    return data.site("target").xpos - data.site("tip").xpos


def apply_joint_step(model, data, joint_ids, dq):
    """Add `dq` to the active joints, clipped to their ranges."""
    for joint_id, delta in zip(joint_ids, dq, strict=True):
        address = model.jnt_qposadr[joint_id]
        low, high = model.jnt_range[joint_id]
        data.qpos[address] = np.clip(data.qpos[address] + delta, low, high)
    mujoco.mj_forward(model, data)


def autocorrect(model, data, active, measure=measure_error, actuate=apply_joint_step,
                tolerance_mm=TOLERANCE_MM, max_iterations=MAX_ITERATIONS):
    """Run the loop and return one dict per iteration. Iteration 0 is the starting pose."""
    site_id = model.site("tip").id
    joint_ids = [model.joint(name).id for name in active]
    dof_ids = [model.jnt_dofadr[j] for j in joint_ids]
    jacobian = np.zeros((3, model.nv))
    rows = []
    previous_tip = None
    for iteration in range(max_iterations + 1):
        mujoco.mj_forward(model, data)
        error = measure(model, data)
        distance_mm = float(np.linalg.norm(error) * 1000.0)
        tip = data.site("tip").xpos.copy()
        step_mm = 0.0 if previous_tip is None else float(np.linalg.norm(tip - previous_tip) * 1000.0)
        previous_tip = tip
        rows.append({
            "iteration": iteration,
            "x_mm": data.qpos[model.joint("x").qposadr[0]] * 1000.0,
            "y_mm": data.qpos[model.joint("y").qposadr[0]] * 1000.0,
            "z_mm": data.qpos[model.joint("z").qposadr[0]] * 1000.0,
            "tilt_y_rad": _qpos_or_zero(model, data, "tilt_y"),
            "tilt_x_rad": _qpos_or_zero(model, data, "tilt_x"),
            "distance_mm": distance_mm,
            "tip_step_mm": step_mm,
        })
        if distance_mm < tolerance_mm or iteration == max_iterations:
            break
        mujoco.mj_jacSite(model, data, jacobian, None, site_id)
        j = jacobian[:, dof_ids]
        dq = j.T @ np.linalg.solve(j @ j.T + DAMPING * np.eye(3), GAIN * error)
        predicted_step = np.linalg.norm(j @ dq)
        if predicted_step > MAX_TIP_STEP_M:
            dq *= MAX_TIP_STEP_M / predicted_step
        actuate(model, data, joint_ids, dq)
    return rows


def _qpos_or_zero(model, data, name):
    try:
        return float(data.qpos[model.joint(name).qposadr[0]])
    except KeyError:
        return 0.0


def write_log(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: f"{value:.6f}" if isinstance(value, float) else value
                             for key, value in row.items()})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="logs/iteraciones.csv", help="CSV log path")
    parser.add_argument("--wrist-active", action="store_true", help="let the wrist axes take part in the correction")
    args = parser.parse_args(argv)

    model, data = sim_brazo.build_model(wrist_dof=2)
    sim_brazo.set_pose(model, data, **START_POSE)
    active = list(sim_brazo.LINEAR_JOINTS) + (list(sim_brazo.WRIST_JOINTS) if args.wrist_active else [])
    rows = autocorrect(model, data, active)
    write_log(rows, args.out)

    final = rows[-1]["distance_mm"]
    largest_step = max(row["tip_step_mm"] for row in rows)
    print(f"iterations: {rows[-1]['iteration']}  rows: {len(rows)}  start: {rows[0]['distance_mm']:.3f} mm  "
          f"final: {final:.6f} mm  largest tip step: {largest_step:.3f} mm  log: {args.out}")
    ok = final < TOLERANCE_MM and len(rows) >= MIN_ROWS and largest_step <= MAX_TIP_STEP_M * 1000.0 + 1e-6
    print("LOOP OK" if ok else "LOOP FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
