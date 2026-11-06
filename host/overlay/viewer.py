"""The viewer: takes frames from a source, draws the overlay on each camera and puts the views side by side in one page.

A source gives, for each step, the tip, the target and a status. `SimSource` is the only one built: it moves a simulated tool tip along a
straight path to a target and shows the status that the controller would report. A video or a live camera needs a source that decodes
the images and a tip detector (cards p1-10 and p1-12); the overlay itself does not change.
"""
import sys
from pathlib import Path

import numpy as np
from coords import SampleFrame, triangulate

from . import scene
from .overlay import OverlayState, explain, view_svg


class SimSource:
    """A simulated approach: `steps` positions from `start` to `target`, with the status of each."""

    def __init__(self, start, target, steps=12, work_y=0.0):
        self.start = np.asarray(start, dtype=float)
        self.target = np.asarray(target, dtype=float)
        self.steps = steps
        self.cameras = scene.default_cameras(work_y)
        self.phantom = scene.block((0.0, work_y, 0.0))
        self.frame = SampleFrame.from_landmarks(origin=(0.0, work_y + 10.0, 0.0), rear_point=(0.0, work_y - 10.0, 0.0))

    def __iter__(self):
        for i in range(self.steps + 1):
            tip = self.start + (self.target - self.start) * i / self.steps
            state = "idle" if i in (0, self.steps) else "moving"
            yield OverlayState(tip, self.target, {"state": state, "homed": True, "cause": "none"}, "injector", self.frame, approved=True)

    def images(self, state):
        return {name: scene.render(P, state.tip, self.phantom) for name, P in self.cameras.items()}


def triangulated_tip(cameras, state):
    """Tip position from cameras A and B alone, as a real run would get it: project, then triangulate (the reprojection residual is dropped)."""
    from coords import project

    point, _residual = triangulate(cameras["A"], cameras["B"], project(cameras["A"], state.tip), project(cameras["B"], state.tip))
    return point


def compose(svgs, titles=("A", "B", "M")):
    """One page with the views in a row."""
    body = "".join(f'<div style="margin:4px">{s}</div>' for s in svgs)
    return f'<!doctype html><meta charset="utf-8"><body style="background:#0F1B2D;margin:0;display:flex;flex-wrap:wrap">{body}</body>'


def run_demo(out_dir, steps=6):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    source = SimSource(start=(-20.0, 25.0, 30.0), target=(5.0, 5.0, 8.0), steps=steps)
    for n, state in enumerate(source):
        images = source.images(state)
        svgs = [view_svg(name, P, images[name], state) for name, P in source.cameras.items()]
        (out / f"frame_{n:02d}.html").write_text(compose(svgs), encoding="utf-8")
        if n in (0, steps):
            for name, P in source.cameras.items():
                for line in explain(name, P, state):
                    print(line)
    print("wrote", steps + 1, "frames to", out)


if __name__ == "__main__":
    run_demo(sys.argv[1] if len(sys.argv) > 1 else "overlay_demo")
