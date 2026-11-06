"""Tests of the overlay viewer on simulated frames. Usage, from the repository root:

    python host/overlay/test_overlay.py

The checks use values that can be computed by hand (a 3-4-5 triangle for the error, the scale of a pinhole camera) and read the drawn
numbers back from the SVG. Exit code 1 on a failure.
"""
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import itertools

from coords import SampleFrame, project

from overlay import (
    OverlayState,
    SimSource,
    elements,
    explain,
    pixels_per_mm,
    png_bytes,
    run_demo,
    scene,
    triangulated_tip,
    view_svg,
)
from overlay.overlay import RED

FAILURES = []


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


def decode_png(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF, "bad crc"
        if kind == b"IHDR":
            width, height = struct.unpack(">II", body[:8])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    rows = [np.frombuffer(raw[r * (1 + 3 * width) + 1:(r + 1) * (1 + 3 * width)], dtype=np.uint8).reshape(width, 3) for r in range(height)]
    return np.array(rows)


def test_png():
    print("png writer")
    image = np.random.default_rng(1).integers(0, 255, (7, 5, 3), dtype=np.uint8)
    check(np.array_equal(decode_png(png_bytes(image)), image), "a PNG written and read back is the same image")
    try:
        png_bytes(np.zeros((4, 4), dtype=np.uint8))
        check(False, "a grey array is refused")
    except ValueError:
        check(True, "a grey array is refused")


def test_scene():
    print("scene")
    cams = scene.default_cameras(0.0)
    for name, P in cams.items():
        px = project(P, (0.0, 0.0, 10.0))
        check(np.allclose(px, (320, 240), atol=1e-6), f"camera {name} sees its aim point at the centre of the image")
    P = cams["A"]
    distance = np.linalg.norm(np.array([0.0, 175.0, 170.0]) - np.array([0.0, 0.0, 10.0]))
    expected = 1400.0 / distance
    along_x = float(np.linalg.norm(project(P, (1.0, 0.0, 10.0)) - project(P, (0.0, 0.0, 10.0))))
    check(abs(along_x - expected) / expected < 0.01, f"scale of camera A along X is f / distance, about {expected:.2f} px/mm ({along_x:.2f})")
    check(0.5 * expected < pixels_per_mm(P, (0.0, 0.0, 10.0)) <= expected * 1.001, "the averaged scale is smaller than that along X, because Z is foreshortened")
    tip = (4.0, 3.0, 12.0)
    image = scene.render(P, tip, scene.block((0.0, 0.0, 0.0)))
    x, y = project(P, tip)
    check(image.shape == (480, 640, 3) and image[round(y), round(x)].min() > 200, "the tip is drawn bright at its projected pixel")
    check(tuple(image[5, 5]) == (16, 24, 38), "the background is dark")


def test_elements():
    print("overlay elements")
    cams = scene.default_cameras(0.0)
    state = OverlayState(np.array([0.0, 0.0, 0.0]), np.array([3.0, 4.0, 0.0]), {"state": "moving", "cause": "none"}, "injector")
    check(abs(state.error_mm - 5.0) < 1e-12, "a 3-4-5 triangle gives an error of 5 mm")
    texts = {name: next(e["text"] for e in elements(name, P, state) if e["kind"] == "error") for name, P in cams.items()}
    check(len({t.split(" ", 1)[1] for t in texts.values()}) == 1 and "5.000 mm" in texts["A"], "the error in mm is the same in every view")
    tips = {name: next(e for e in elements(name, P, state) if e["kind"] == "tip")["px"] for name, P in cams.items()}
    for name, P in cams.items():
        check(np.allclose(tips[name], project(P, state.tip)), f"{name}: the tip marker is at the projection of the tip")
    kinds = [e["kind"] for e in elements("A", cams["A"], state)]
    check(kinds == ["tip", "target", "error", "scale", "banner"], f"no anatomy line without a sample frame ({kinds})")
    frame = SampleFrame.from_landmarks(origin=(0.0, 10.0, 0.0), rear_point=(0.0, -10.0, 0.0))
    state.frame = frame
    state.tip = np.array([0.0, 12.0, 0.0])  # 2 mm in front of the origin landmark... towards the user is anterior here
    anatomy = next(e for e in elements("A", cams["A"], state) if e["kind"] == "anatomy")
    ap, ml, dv = frame.to_sample(state.tip)
    check(f"AP {ap:+.2f}" in anatomy["text"] and abs(ap - 2.0) < 1e-9 and abs(ml) < 1e-9 and abs(dv) < 1e-9, f"anatomical text from the frame ({anatomy['text']})")


def test_banner_colours():
    print("red is only for a stop or a fault")
    cams = scene.default_cameras(0.0)
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    for st, red in (("idle", False), ("moving", False), ("abort", True), ("fault", True)):
        state = OverlayState(np.zeros(3), np.ones(3), {"state": st, "cause": "stop_button" if st == "abort" else "none"}, "probe")
        svg = view_svg("A", cams["A"], image, state)
        check((RED in svg) == red, f"state {st}: the banner {'is' if red else 'is not'} red")
        check(st in svg, f"state {st}: the state is written on the banner")
    check("stop_button" in view_svg("A", cams["A"], image, OverlayState(np.zeros(3), np.ones(3), {"state": "abort", "cause": "stop_button"})),
          "the cause of an abort is on the banner")
    check("not approved" in view_svg("A", cams["A"], image, OverlayState(np.zeros(3), np.ones(3), {"state": "idle"})), "a move without approval says so")


def test_svg_numbers():
    print("the SVG carries the numbers")
    cams = scene.default_cameras(0.0)
    tip = np.array([1.0, 2.0, 3.0])
    state = OverlayState(tip, np.array([2.0, 2.0, 3.0]), {"state": "idle"}, "scalpel", approved=True)
    image = scene.render(cams["B"], tip, scene.block((0.0, 0.0, 0.0)))
    root = ET.fromstring(view_svg("B", cams["B"], image, state))
    ns = "{http://www.w3.org/2000/svg}"
    tip_g = next(g for g in root.iter(ns + "g") if g.get("data-kind") == "tip")
    px = project(cams["B"], tip)
    check(abs(float(tip_g.get("data-x")) - px[0]) < 0.01 and abs(float(tip_g.get("data-y")) - px[1]) < 0.01, "the tip marker coordinates are the projection")
    target = next(c for c in root.iter(ns + "circle") if c.get("data-kind") == "target")
    tp = project(cams["B"], state.target)
    check(abs(float(target.get("cx")) - tp[0]) < 0.01, "the target circle is at the projection of the target")
    href = next(iter(root.iter(ns + "image"))).get("href")
    check(href.startswith("data:image/png;base64,"), "the frame is embedded as a PNG")
    check("approved" in "".join(t.text or "" for t in root.iter(ns + "text")) or "approved" in ET.tostring(root, encoding="unicode"), "the approval is shown")


def test_triangulation_and_source():
    print("triangulated tip and the simulated source")
    source = SimSource(start=(-20.0, 25.0, 30.0), target=(5.0, 5.0, 8.0), steps=8)
    states = list(source)
    check(len(states) == 9, "a source of 8 steps gives 9 states")
    check(states[0].status["state"] == "idle" and states[-1].status["state"] == "idle" and states[4].status["state"] == "moving", "idle at both ends, moving in between")
    errors = [s.error_mm for s in states]
    check(all(a > b for a, b in itertools.pairwise(errors)) and errors[-1] < 1e-9, "the error goes down at every step to zero")
    got = triangulated_tip(source.cameras, states[3])
    check(np.allclose(got, states[3].tip, atol=1e-6), "two cameras give back the tip position")
    images = source.images(states[2])
    check(set(images) == {"A", "B", "M"} and all(im.shape == (480, 640, 3) for im in images.values()), "a frame for each of the three views")


def test_explain_and_demo():
    print("explanations and demo")
    cams = scene.default_cameras(0.0)
    state = OverlayState(np.zeros(3), np.array([1.0, 0.0, 0.0]), {"state": "idle"}, "injector")
    lines = explain("A", cams["A"], state)
    check(len(lines) == len(elements("A", cams["A"], state)) and all(len(line.split(": ")) >= 4 for line in lines), "one explanation per element, with a how")
    with tempfile.TemporaryDirectory() as tmp:
        run_demo(tmp, steps=3)
        pages = sorted(Path(tmp).glob("frame_*.html"))
        check(len(pages) == 4 and all("<svg" in p.read_text(encoding="utf-8") for p in pages), "the demo writes one page per step with the three views")


def main():
    for test in (test_png, test_scene, test_elements, test_banner_colours, test_svg_numbers, test_triangulation_and_source, test_explain_and_demo):
        test()
    print("OVERLAY OK" if not FAILURES else f"OVERLAY FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
