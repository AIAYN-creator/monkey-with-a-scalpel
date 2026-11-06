"""The overlay: what is drawn over each camera view and why. Every element comes with a sentence that says how its number was computed
(`explain`), so the viewer can show the reasoning and a test can check it.

Colour rules (see the brand notes): amber means "look here" (the target and the error), red only means a stop or a fault, bone is the
tool. Output is SVG: the frame as an embedded PNG with live text and vector shapes on top, so it scales and can be tested by reading
the numbers back.
"""
from dataclasses import dataclass, field

import numpy as np
from coords import project

from .png import data_uri

BONE, AMBER, RED, INK, SLATE = "#EAF2F8", "#F5A524", "#E5484D", "#0F1B2D", "#8FA3B8"
FAULT_STATES = ("abort", "fault", "estop")


@dataclass
class OverlayState:
    tip: np.ndarray  # tip position in machine mm (the triangulated one in real use, the simulated one here)
    target: np.ndarray  # target in machine mm
    status: dict = field(default_factory=dict)  # a parsed STATUS reply: state, homed, cause, axes
    tool: str = ""  # name of the mounted tool
    frame: object = None  # a coords.SampleFrame, for the anatomical coordinates
    approved: bool = False  # whether a human approved the move shown (the LLM interface sets it)

    @property
    def error_vector(self):
        return np.asarray(self.target, dtype=float) - np.asarray(self.tip, dtype=float)

    @property
    def error_mm(self):
        return float(np.linalg.norm(self.error_vector))


def pixels_per_mm(P, point):
    """Scale of the view at `point`: the pixel distance of two points 1 mm apart along X, and along Z, averaged."""
    p = np.asarray(point, dtype=float)
    sx = np.linalg.norm(project(P, p + [1.0, 0, 0]) - project(P, p))
    sz = np.linalg.norm(project(P, p + [0, 0, 1.0]) - project(P, p))
    return float((sx + sz) / 2)


def elements(name, P, state):
    """The overlay of one view as a list of dicts: kind, pixel position(s), text and how it was computed."""
    tip_px = project(P, state.tip)
    target_px = project(P, state.target)
    scale = pixels_per_mm(P, state.target)
    items = [
        {"kind": "tip", "px": tuple(tip_px), "text": "tip", "how": "the tip position projected with this camera's matrix P"},
        {"kind": "target", "px": tuple(target_px), "text": "target", "how": "the target projected with the same matrix"},
        {"kind": "error", "px": (tuple(tip_px), tuple(target_px)),
         "text": f"error {state.error_mm:.3f} mm",
         "how": "the length of target - tip in machine mm (not the pixel distance, which depends on the view)"},
        {"kind": "scale", "px": scale, "text": f"{scale:.1f} px/mm",
         "how": "the pixel distance of two points 1 mm apart, along X and Z, at the target, averaged"},
    ]
    status = state.status or {}
    label = status.get("state", "unknown")
    if status.get("cause", "none") not in ("none", ""):
        label += f" ({status['cause']})"
    items.append({"kind": "banner", "text": f"{name}  {label}  tool: {state.tool or 'none'}  "
                  f"{'approved' if state.approved else 'not approved'}",
                  "alert": status.get("state") in FAULT_STATES,
                  "how": "the state and cause of the last STATUS reply of the controller; red only for abort, fault or e-stop"})
    if state.frame is not None:
        ap, ml, dv = state.frame.to_sample(state.tip)
        items.append({"kind": "anatomy", "text": f"AP {ap:+.2f}  ML {ml:+.2f}  DV {dv:+.2f} mm",
                      "how": "the tip in the sample frame fixed by the two landmarks (coords.SampleFrame.to_sample)"})
    return items


def view_svg(name, P, image, state, size=(640, 480)):
    """SVG of one view: the frame and the overlay of `elements`."""
    w, h = size
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="Arial, sans-serif">',
           f'<image href="{data_uri(image)}" width="{w}" height="{h}"/>']
    for e in elements(name, P, state):
        kind = e["kind"]
        if kind == "tip":
            x, y = e["px"]
            out.append(f'<g data-kind="tip" data-x="{x:.2f}" data-y="{y:.2f}" stroke="{BONE}" stroke-width="1.5" fill="none">'
                       f'<line x1="{x - 12:.2f}" y1="{y:.2f}" x2="{x + 12:.2f}" y2="{y:.2f}"/>'
                       f'<line x1="{x:.2f}" y1="{y - 12:.2f}" x2="{x:.2f}" y2="{y + 12:.2f}"/></g>')
        elif kind == "target":
            x, y = e["px"]
            out.append(f'<circle data-kind="target" data-x="{x:.2f}" data-y="{y:.2f}" cx="{x:.2f}" cy="{y:.2f}" r="9" fill="none" '
                       f'stroke="{AMBER}" stroke-width="2"/>')
        elif kind == "error":
            (x1, y1), (x2, y2) = e["px"]
            out.append(f'<line data-kind="error" x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{AMBER}" '
                       f'stroke-width="1.5" stroke-dasharray="4 3"/>'
                       f'<text x="{(x1 + x2) / 2 + 8:.2f}" y="{(y1 + y2) / 2 - 8:.2f}" fill="{AMBER}" font-size="14">{e["text"]}</text>')
        elif kind == "scale":
            bar = e["px"] * 1.0
            out.append(f'<g data-kind="scale"><rect x="16" y="{h - 28}" width="{bar:.1f}" height="4" fill="{BONE}"/>'
                       f'<text x="16" y="{h - 34}" fill="{BONE}" font-size="12">1 mm  ({e["text"]})</text></g>')
        elif kind == "banner":
            colour = RED if e["alert"] else INK
            out.append(f'<g data-kind="banner"><rect x="0" y="0" width="{w}" height="26" fill="{colour}" opacity="0.85"/>'
                       f'<text x="10" y="18" fill="{BONE}" font-size="14">{e["text"]}</text></g>')
        elif kind == "anatomy":
            out.append(f'<text data-kind="anatomy" x="{w - 10}" y="{h - 12}" fill="{BONE}" font-size="14" text-anchor="end">{e["text"]}</text>')
    out.append("</svg>")
    return "\n".join(out)


def explain(name, P, state):
    """One line per overlay element: what it shows and how its number was obtained."""
    return [f"{name}: {e['kind']}: {e['text']}: {e['how']}" for e in elements(name, P, state)]
