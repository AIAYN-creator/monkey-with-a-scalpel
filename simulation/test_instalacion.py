"""Installation check for the simulation stack (card p0-01).

Core check: import mujoco and numpy, create an empty world, step it, close it.
Extra check: offscreen rendering, which Phase 0 needs for the timelapse video.
Exit code is 0 only if the core check passes; the render check is reported on its own.
"""
import sys

import mujoco
import numpy as np

EMPTY_WORLD = "<mujoco/>"

RENDER_WORLD = """
<mujoco>
  <visual><global offwidth="320" offheight="240"/></visual>
  <worldbody>
    <light pos="0 0 2" dir="0 0 -1"/>
    <geom type="plane" size="1 1 0.1" rgba="0.8 0.8 0.8 1"/>
    <geom type="sphere" pos="0 0 0.1" size="0.1" rgba="1 0 0 1"/>
    <camera name="top" pos="0 -0.6 0.5" xyaxes="1 0 0 0 0.6 0.8"/>
  </worldbody>
</mujoco>
"""


def core_check():
    print(f"python  {sys.version.split()[0]}")
    print(f"numpy   {np.__version__}")
    print(f"mujoco  {mujoco.__version__}")
    model = mujoco.MjModel.from_xml_string(EMPTY_WORLD)
    data = mujoco.MjData(model)
    mujoco.mj_step(model, data)
    print(f"empty world: nbody={model.nbody} ngeom={model.ngeom} time={data.time:.4f}")
    del data, model
    print("CORE OK")


def render_check():
    model = mujoco.MjModel.from_xml_string(RENDER_WORLD)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    with mujoco.Renderer(model, height=240, width=320) as renderer:
        renderer.update_scene(data, camera="top")
        frame = renderer.render()
    red = int(np.sum((frame[..., 0] > 150) & (frame[..., 1] < 80) & (frame[..., 2] < 80)))
    print(f"frame shape={frame.shape} dtype={frame.dtype} red_pixels={red}")
    if red == 0:
        raise RuntimeError("frame rendered but the red sphere is not visible")
    print("RENDER OK")


if __name__ == "__main__":
    core_check()
    try:
        render_check()
    except Exception as exc:  # noqa: BLE001 - any rendering backend failure is reported, not fatal
        print(f"RENDER FAILED: {type(exc).__name__}: {exc}")
