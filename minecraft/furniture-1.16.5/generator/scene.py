"""Showcase scene for the terrain pieces: bare blocky terrain (left) vs the same terrain dressed (right)."""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from furngen import NORMAL, Model, axis_rot, euler, face_corners, rotate_point
import models_terrain as T

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "terrain-1.16.5", "previews")


def grass_block():
    m = Model("grass_block", 4)
    m.box("cube", (0, 0, 0), (16, 16, 16), T.terrain(lambda x, z: 16 + 0 * x, band=1.6, seed=50), skip=("down",))
    m.build(size=256)
    return m


def built(fn):
    m = fn()
    m.dens = 4.0
    m.build(size=256)
    return m


def scene_faces(instances):
    for m, off, rot in instances:
        R = axis_rot("y", rot)
        atlas = m.atlas.astype(float) / 255.0
        for el in m.elements:
            for d, f in el.faces.items():
                r = f["rect"]
                cs = [R @ (rotate_point(p, el.rot) - 8.0) + 8.0 + off for p in face_corners(el.frm, el.to, d)]
                n = np.array(NORMAL[d], float)
                if el.rot:
                    n = axis_rot(el.rot[0], el.rot[1]) @ n
                yield cs, R @ n, atlas, (r["ax"], r["ay"], r["pw"], r["ph"]), el.shade


def render_scene(instances, view=(32, 208, 0), W=1800, H=1050, ssaa=2, pad=0.06):
    V = euler(*view)
    faces = list(scene_faces(instances))
    pts = np.array([V @ p for f in faces for p in f[0]])
    lo, hi = pts[:, :2].min(0), pts[:, :2].max(0)
    Wp, Hp = W * ssaa, H * ssaa
    k = min(Wp / (hi[0] - lo[0]), Hp / (hi[1] - lo[1])) * (1 - 2 * pad)
    cen = (lo + hi) / 2
    color = np.zeros((Hp, Wp, 3))
    depth = np.full((Hp, Wp), -1e9)
    ys, xs = np.mgrid[0:Hp, 0:Wp] + 0.5
    L = np.array([-0.35, 1.0, -0.55]); L /= np.linalg.norm(L)
    for cs, n, atlas, (ax, ay, pw, ph), shade_on in faces:
        nv = V @ n
        if nv[2] <= 1e-6:
            continue
        P = [V @ p for p in cs]
        scr = [np.array([(p[0] - cen[0]) * k + Wp / 2, Hp / 2 - (p[1] - cen[1]) * k]) for p in P]
        s00, s10, s01 = scr
        e1, e2 = s10 - s00, s01 - s00
        det = e1[0] * e2[1] - e1[1] * e2[0]
        if abs(det) < 1e-9:
            continue
        q = np.array([s00, s10, s01, s10 + e2])
        x0, y0 = np.maximum(np.floor(q.min(0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(q.max(0)).astype(int), [Wp, Hp])
        if x0 >= x1 or y0 >= y1:
            continue
        px = xs[y0:y1, x0:x1] - s00[0]
        py = ys[y0:y1, x0:x1] - s00[1]
        a = (px * e2[1] - py * e2[0]) / det
        b = (e1[0] * py - e1[1] * px) / det
        ins = (a >= 0) & (a < 1) & (b >= 0) & (b < 1)
        if not ins.any():
            continue
        z = P[0][2] + a * (P[1][2] - P[0][2]) + b * (P[2][2] - P[0][2])
        tu = np.clip((ax + a * pw).astype(int), ax, ax + pw - 1)
        tv = np.clip((ay + b * ph).astype(int), ay, ay + ph - 1)
        tex = atlas[tv, tu]
        vis = ins & (tex[..., 3] > 0.1) & (z > depth[y0:y1, x0:x1])
        if not vis.any():
            continue
        sh = (0.5 + 0.55 * max(0.0, float(n @ L))) if shade_on else 0.95
        color[y0:y1, x0:x1][vis] = tex[..., :3][vis] * min(sh, 1.0)
        depth[y0:y1, x0:x1][vis] = z[vis]
    # gloomy sky gradient + fog by depth
    sky = np.linspace(0.30, 0.16, Hp)[:, None, None] * np.array([0.78, 0.82, 0.86])
    bg = depth < -1e8
    color[bg] = np.broadcast_to(sky, color.shape)[bg]
    dn = depth.copy(); dn[bg] = np.nan
    if np.isfinite(dn).any():
        fz = (np.nanmax(dn) - dn) / (np.nanmax(dn) - np.nanmin(dn) + 1e-9)
        f = np.nan_to_num(np.clip(fz * 0.28, 0, 0.28))[..., None]
        color = color * (1 - f) + np.array([0.24, 0.26, 0.27]) * f
    img = Image.fromarray((np.clip(color, 0, 1) * 255).astype(np.uint8), "RGB")
    return img.resize((W, H), Image.LANCZOS)


def terrain_layout(dressed, gb, P, ox=0.0):
    """Ground at y=-1, a 1-high plateau with a protrusion, a 2nd tier at the back."""
    inst = []
    B = 16.0
    X, Z = 10, 8
    def blk(x, y, z):
        inst.append((gb, np.array([ox + x * B, y * B, z * B]), 0))
    plateau = {(x, z) for x in range(X) for z in range(4, Z)} | {(4, 3), (5, 3), (6, 3)}
    tier2 = {(x, z) for x in range(X) for z in range(6, Z)}
    for x in range(X):
        for z in range(Z):
            blk(x, -1, z)
            if (x, z) in plateau:
                blk(x, 0, z)
            if (x, z) in tier2:
                blk(x, 1, z)
    if not dressed:
        return inst
    def put(name, x, y, z, rot=0):
        inst.append((P[name], np.array([ox + x * B, y * B, z * B]), rot))
    for x in range(X):
        if (x, 3) not in plateau:
            put("terrain_slope", x, 0, 3)
    for x in (4, 5, 6):
        put("terrain_slope", x, 0, 2)
    put("terrain_slope_inner", 3, 0, 3)            # plateau to the south and east
    put("terrain_slope_inner", 7, 0, 3, -90)       # plateau to the south and west
    put("terrain_slope_outer", 3, 0, 2)            # protrusion to the south-east
    put("terrain_slope_outer", 7, 0, 2, -90)       # protrusion to the south-west
    for x in range(X):
        put("terrain_grass_overhang", x, 2, 6)     # lip on top of the 2nd tier, hanging north
        if x % 3 != 1:
            put("terrain_cliff_rocks", x, 1, 5)    # rocks against the 2nd-tier wall
    put("terrain_rocks", 1, 0, 1); put("terrain_rocks", 8, 1, 4, 90)
    for (x, z) in ((0, 0), (2, 1), (5, 0), (8, 0), (9, 1), (1, 2)):
        put("terrain_grass_tuft", x, 0, z)
    for (x, z) in ((1, 5), (4, 4), (6, 5), (9, 4)):
        put("terrain_grass_tuft", x, 1, z)
    put("terrain_mound", 4, 0, 0); put("terrain_mound", 2, 1, 4)
    return inst


def main():
    os.makedirs(OUT, exist_ok=True)
    gb = grass_block()
    P = {n: built(fn) for n, (fn, _, _) in T.MODELS.items()}
    for n, m in P.items():
        print(n, "ok")
    bare = render_scene(terrain_layout(False, gb, P), W=1100, H=760)
    dressed = render_scene(terrain_layout(True, gb, P), W=1100, H=760)
    W, H = bare.size
    out = Image.new("RGB", (W * 2 + 30, H + 90), (22, 24, 26))
    out.paste(bare, (10, 80)); out.paste(dressed, (W + 20, 80))
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    d.text((30, 20), "ДО: обычные блоки", fill=(200, 196, 180), font=font)
    d.text((W + 40, 20), "ПОСЛЕ: склоны, трава, камни", fill=(200, 196, 180), font=font)
    out.save(os.path.join(OUT, "showcase.png"))
    dressed.save(os.path.join(OUT, "showcase_after.png"))
    print("saved", os.path.join(OUT, "showcase.png"))


if __name__ == "__main__":
    main()
