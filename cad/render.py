"""Render the STL files written by build.py into overview sheets (PNG), using MuJoCo's offscreen renderer.

Usage, from the repository root:
    python cad/render.py STL_DIR OUT_DIR
"""
import json
import shutil
import struct
import sys
import tempfile
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PRINTED = (0.95, 0.55, 0.15)
MACHINED = (0.68, 0.71, 0.76)
INK, MUTED, RED = (31, 41, 51), (82, 96, 109), (200, 40, 40)


def font(name, size):
    return ImageFont.truetype(rf"C:\Windows\Fonts\{name}", size)


def stl_vertices(path):
    """All vertices of an STL file (binary or ASCII), in the file's units."""
    raw = Path(path).read_bytes()
    if raw[:5] == b"solid" and b"facet" in raw[:400]:
        values = [list(map(float, line.split()[1:4])) for line in raw.decode().splitlines() if line.strip().startswith("vertex")]
        return np.array(values)
    count = struct.unpack("<I", raw[80:84])[0]
    data = np.frombuffer(raw[84:84 + count * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    return data["v"].reshape(-1, 3)


def render(items, az, el, size, margin=1.15):
    """Render STL items [(path, (r, g, b, a))], framed on their joint bounding box. Lengths in mm."""
    tmp = Path(tempfile.mkdtemp(prefix="rd"))
    verts = []
    assets, geoms = [], []
    for i, (path, rgba) in enumerate(items):
        shutil.copy(path, tmp / f"m{i}.stl")
        verts.append(stl_vertices(path))
        assets.append(f'<mesh name="m{i}" file="m{i}.stl" scale="0.001 0.001 0.001"/>')
        geoms.append(f'<geom type="mesh" mesh="m{i}" rgba="{rgba[0]} {rgba[1]} {rgba[2]} {rgba[3]}"/>')
    allv = np.vstack(verts) / 1000.0
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    centre, extent = (lo + hi) / 2, float(np.linalg.norm(hi - lo))
    w, h = size
    xml = f"""
<mujoco>
  <visual><global offwidth="{w}" offheight="{h}" fovy="30"/><quality offsamples="8" shadowsize="4096"/>
    <headlight ambient="0.5 0.5 0.5" diffuse="0.55 0.55 0.55" specular="0.1 0.1 0.1"/></visual>
  <asset><texture type="skybox" builtin="gradient" rgb1="1 1 1" rgb2="0.93 0.95 0.97" width="64" height="64"/>{"".join(assets)}</asset>
  <default><geom contype="0" conaffinity="0"/></default>
  <worldbody>
    <light pos="{centre[0] + 0.3} {centre[1] - 0.4} {hi[2] + 0.5}" dir="-0.4 0.6 -0.8" diffuse="0.7 0.7 0.7"/>
    <geom type="plane" size="2 2 0.01" pos="0 0 {lo[2] - 0.004}" rgba="0.97 0.97 0.98 1"/>
    {"".join(geoms)}
  </worldbody>
</mujoco>"""
    (tmp / "scene.xml").write_text(xml, encoding="utf-8")
    model = mujoco.MjModel.from_xml_path(str(tmp / "scene.xml"))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.azimuth, cam.elevation, cam.distance = az, el, extent * 1.5 * margin
    cam.lookat[:] = centre
    with mujoco.Renderer(model, height=h, width=w) as renderer:
        renderer.update_scene(data, camera=cam)
        image = Image.fromarray(renderer.render())
    shutil.rmtree(tmp, ignore_errors=True)
    return image


def parts_sheet(stl_dir, out_png, cols=5, tile_w=520, tile_h=440):
    info = json.loads((stl_dir / "report.json").read_text())["parts"]
    head = 120
    rows = -(-len(info) // cols)
    sheet = Image.new("RGB", (cols * tile_w, head + rows * tile_h), "white")
    d = ImageDraw.Draw(sheet)
    big = 44 if cols >= 5 else 38
    d.text((sheet.width / 2, 24), "Vernier: planos provisionales v0.2, piezas", font=font("segoeuib.ttf", big), fill=INK, anchor="ma")
    d.text((sheet.width / 2, 82), "Medidas supuestas o típicas de catálogo; ninguna es una medición. No imprimir todavía.", font=font("segoeui.ttf", 26),
           fill=RED, anchor="ma")
    for k, row in enumerate(info):
        color = MACHINED if row["kind"] == "machined" else PRINTED
        img = render([(stl_dir / f"{row['part']}.stl", (*color, 1.0))], az=140, el=-28, size=(tile_w - 20, tile_h - 90))
        x, y = (k % cols) * tile_w, head + (k // cols) * tile_h
        sheet.paste(img, (x + 10, y + 4))
        d.rectangle((x + 10, y + 4, x + tile_w - 10, y + tile_h - 86), outline=(205, 210, 217), width=2)
        d.text((x + 16, y + tile_h - 80), row["part"], font=font("segoeuib.ttf", 26), fill=INK)
        sx, sy, sz = row["size_mm"]
        kind = "mecanizada (aluminio)" if row["kind"] == "machined" else "impresa"
        d.text((x + 16, y + tile_h - 46), f"{sx:g} x {sy:g} x {sz:g} mm  ·  {row['volume_cm3']:g} cm3  ·  {kind}", font=font("segoeui.ttf", 21),
               fill=MUTED)
    sheet.save(out_png)


def assembly_sheet(stl_dir, out_png):
    colors = {
        "hamilton_clamp": (0.95, 0.55, 0.15, 1.0),
        "tool_backplate": (0.85, 0.45, 0.10, 1.0),
        "plunger_motor_mount": (0.98, 0.75, 0.20, 1.0),
        "plunger_coupler": (0.85, 0.25, 0.25, 1.0),
        "syringe_barrel": (0.65, 0.82, 0.95, 0.55),
        "syringe_plunger": (0.75, 0.78, 0.82, 1.0),
        "syringe_needle": (0.15, 0.15, 0.18, 1.0),
        "actuator_body": (0.25, 0.27, 0.32, 1.0),
        "actuator_shaft": (0.80, 0.82, 0.86, 1.0),
    }
    items = [(stl_dir / f"head_{name}.stl", rgba) for name, rgba in colors.items()]
    views = (("Isométrica", 305, -20), ("Alzado", 270, 0), ("Lateral", 0, 0))
    w, h = 700, 1000
    sheet = Image.new("RGB", (3 * w + 40, h + 330), "white")
    d = ImageDraw.Draw(sheet)
    d.text((sheet.width / 2, 24), "Cabezal de herramienta: ensamblaje provisional v0.1", font=font("segoeuib.ttf", 44), fill=INK, anchor="ma")
    d.text((sheet.width / 2, 82), "Émbolo a mitad de carrera. Jeringa, aguja y actuador son maquetas, no piezas a fabricar.",
           font=font("segoeui.ttf", 26), fill=RED, anchor="ma")
    for k, (label, az, el) in enumerate(views):
        img = render(items, az, el, (w, h), margin=1.5)
        sheet.paste(img, (10 + k * (w + 10), 130))
        d.rectangle((10 + k * (w + 10), 130, 10 + k * (w + 10) + w, 130 + h), outline=(205, 210, 217), width=2)
        d.text((30 + k * (w + 10), 140), label, font=font("segoeuib.ttf", 30), fill=MUTED)
    legend = [("Soporte de la Hamilton", colors["hamilton_clamp"]), ("Placa del cabezal", colors["tool_backplate"]),
              ("Soporte del motor del émbolo", colors["plunger_motor_mount"]), ("Acoplamiento del émbolo", colors["plunger_coupler"]),
              ("Jeringa (maqueta)", colors["syringe_barrel"]), ("Actuador NEMA 11 (maqueta)", colors["actuator_body"])]
    y0 = 130 + h + 30
    for k, (name, c) in enumerate(legend):
        x = 30 + (k % 3) * 700
        y = y0 + (k // 3) * 48
        d.rectangle((x, y + 4, x + 30, y + 34), fill=tuple(int(v * 255) for v in c[:3]))
        d.text((x + 44, y), name, font=font("segoeui.ttf", 28), fill=INK)
    d.text((30, y0 + 120), "Aguja hacia abajo. El pivote de una muñeca futura iría en el plano del casquillo (z = 0), para acortar la palanca hasta la punta.",
           font=font("segoeui.ttf", 24), fill=MUTED)
    sheet.save(out_png)


SYSTEM_COLORS = (
    (("phantom_block",), (0.35, 0.75, 0.45, 0.45)),
    (("syringe_barrel",), (0.65, 0.82, 0.95, 0.6)),
    (("syringe_needle", "syringe_plunger", "actuator_shaft"), (0.15, 0.15, 0.18, 1.0)),
    (("cam_a", "cam_b", "actuator_body", "_motor", "_screw", "electronics_box", "_switch_l", "_switch_r"), (0.22, 0.25, 0.30, 1.0)),
    (("base_plate", "y_plate", "z_plate", "z_riser", "crossbeam_rod"), (0.72, 0.75, 0.80, 1.0)),
    (("upright", "_post", "_rail", "_carriage"), (0.55, 0.58, 0.63, 1.0)),
)


def system_color(name):
    for keys, rgba in SYSTEM_COLORS:
        if any(k in name for k in keys):
            return rgba
    return (0.95, 0.55, 0.15, 1.0)


def system_items(stl_dir, tag):
    prefix = f"{tag}_"
    return [(p, system_color(p.stem[len(prefix):])) for p in sorted(stl_dir.glob(f"{prefix}*.stl"))]


def system_sheet(stl_dir, out_png):
    w, h = 880, 860
    views = [
        ("Sistema con el cabezal fijo: isométrica", "sysfixed", 305, -25),
        ("Alzado (desde el usuario)", "sysfixed", 270, 0),
        ("Perfil", "sysfixed", 0, 0),
        ("Con muñeca activa, nivelada", "syswrist", 305, -25),
        ("Muñeca inclinada 25° (perfil)", "syswristtilt", 0, 0),
        ("Muñeca inclinada 25°", "syswristtilt", 305, -25),
    ]
    sheet = Image.new("RGB", (3 * w + 40, 2 * (h + 40) + 330), "white")
    d = ImageDraw.Draw(sheet)
    d.text((sheet.width / 2, 24), "Vernier: sistema completo, planos provisionales v0.2", font=font("segoeuib.ttf", 46), fill=INK, anchor="ma")
    d.text((sheet.width / 2, 86), "Medidas supuestas o típicas de catálogo; ninguna es una medición. Motores, tornillos, perfiles y cámaras son maquetas. No imprimir todavía.",
           font=font("segoeui.ttf", 26), fill=RED, anchor="ma")
    for k, (label, tag, az, el) in enumerate(views):
        img = render(system_items(stl_dir, tag), az, el, (w, h), margin=1.0)
        x, y = 10 + (k % 3) * (w + 10), 140 + (k // 3) * (h + 40)
        sheet.paste(img, (x, y))
        d.rectangle((x, y, x + w, y + h), outline=(205, 210, 217), width=2)
        d.text((x + 16, y + 10), label, font=font("segoeuib.ttf", 28), fill=MUTED)
    legend = [("Impresa (PETG/ASA)", (0.95, 0.55, 0.15)), ("Aluminio mecanizado", (0.72, 0.75, 0.80)), ("Perfil, carril, carro (comprados)", (0.55, 0.58, 0.63)),
              ("Motor, cámara, electrónica (maqueta)", (0.22, 0.25, 0.30)), ("Fantoma (maqueta)", (0.35, 0.75, 0.45))]
    y0 = 140 + 2 * (h + 40) + 10
    for k, (name, c) in enumerate(legend):
        x, y = 30 + (k % 3) * 900, y0 + (k // 3) * 48
        d.rectangle((x, y + 4, x + 30, y + 34), fill=tuple(int(v * 255) for v in c))
        d.text((x + 44, y), name, font=font("segoeui.ttf", 28), fill=INK)
    sheet.save(out_png)


if __name__ == "__main__":
    stl, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    parts_sheet(stl, out / "partes.png")
    parts_sheet(stl, out / "partes_vertical.png", cols=3, tile_w=600, tile_h=500)
    assembly_sheet(stl, out / "ensamblaje_cabezal.png")
    system_sheet(stl, out / "sistema_completo.png")
    print("saved", out)
