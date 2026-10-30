"""Error model for the self-correction loop (card p0-04).

Plugs into `loop_autocorreccion.autocorrect` through its two hooks:
  - `make_measure`: what the cameras report, with noise and a constant calibration bias;
  - `make_actuator`: what the axes really do, with backlash and a finite step.

All values are assumptions to explore the loop's tolerance to errors, not measurements of real
hardware. Phase 1 replaces them with measured values (p1-09 and p1-11) and p1-14 compares the
simulation against reality.
"""
from dataclasses import dataclass

import loop_autocorreccion as loop
import mujoco
import numpy as np


@dataclass(frozen=True)
class ErrorModel:
    backlash_mm: float = 0.0  # total play of each linear axis (dead band), in mm
    wrist_play_rad: float = 0.0  # total play of each wrist axis, in rad
    noise_mm: float = 0.0  # standard deviation of the camera noise on each coordinate, in mm
    bias_mm: float = 0.0  # constant calibration error of the measurement, along (1, 1, 1), in mm
    step_mm: float = 0.0  # smallest move an axis can make (0 = continuous), in mm


def make_measure(error_model, rng):
    """Return a `measure(model, data)` that adds calibration bias and camera noise to the true error."""
    bias = error_model.bias_mm / 1000.0 * np.ones(3) / np.sqrt(3.0)
    sigma = error_model.noise_mm / 1000.0

    def measure(model, data):
        error = loop.measure_error(model, data) + bias
        if sigma > 0.0:
            error = error + rng.normal(0.0, sigma, 3)
        return error

    return measure


def make_actuator(error_model):
    """Return an `actuate(model, data, joint_ids, dq)` where the load follows the motor with backlash.

    The controller commands the motor. The load (the joint the tip depends on) only moves once the
    motor has crossed half of the play in either direction, so a reversal first has to take up the
    slack. The motor can also only stop on multiples of `step_mm`.
    """
    motor_position = {}

    def actuate(model, data, joint_ids, dq):
        for joint_id, delta in zip(joint_ids, dq, strict=True):
            address = model.jnt_qposadr[joint_id]
            linear = model.jnt_type[joint_id] == mujoco.mjtJoint.mjJNT_SLIDE
            play = (error_model.backlash_mm / 1000.0) if linear else error_model.wrist_play_rad
            step = error_model.step_mm / 1000.0 if linear else 0.0
            low, high = model.jnt_range[joint_id]
            load = data.qpos[address]
            motor = np.clip(motor_position.get(joint_id, load) + delta, low, high)
            if step > 0.0:
                motor = round(motor / step) * step
            if motor - load > play / 2.0:
                load = motor - play / 2.0
            elif motor - load < -play / 2.0:
                load = motor + play / 2.0
            motor_position[joint_id] = motor
            data.qpos[address] = np.clip(load, low, high)
        mujoco.mj_forward(model, data)

    return actuate
