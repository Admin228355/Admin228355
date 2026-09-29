"""Tiny software renderer for previews (orthographic, z-buffer, nearest texture sampling).

Uses the same math as the game: element rotation around its origin, then the display
transform  v' = T + R * (S * (v - 8)),  R built like Minecraft's Quaternion(x, y, z).
"""
import numpy as np
from PIL import Image

from furngen import DIRS, NORMAL, euler, face_corners, rotate_point, axis_rot

SHADE = {"up": 1.0, "down": 0.5, "north": 0.8, "south": 0.8, "west": 0.6, "east": 0.6}


def _faces(model):
    S = model.S
    for el in model.elements:
        for d, f in el.faces.items():
            r = f["rect"]
            corners = [rotate_point(p, el.rot) for p in face_corners(el.frm, el.to, d)]
            n = np.array(NORMAL[d], float)
            if el.rot:
                n = axis_rot(el.rot[0], el.rot[1]) @ n
            yield corners, n, (r["ax"], r["ay"], r["pw"], r["ph"]), d, el.shade


def render(model, rotation=(25, 205, 0), size=512, fit=True, units=None, bg=(0, 0, 0, 0), ssaa=2,
           translation=(0, 0, 0), scale=1.0):
    R = euler(*rotation)
    N = size * ssaa
    faces = list(_faces(model))
    tr = np.array(translation, float)
    allp = np.array([tr + R @ (scale * (p - 8.0)) for c, *_ in faces for p in c + [c[1] + c[2] - c[0]]])
    if fit:
        lo, hi = allp[:, :2].min(0), allp[:, :2].max(0)
        span = max(hi - lo) * 1.12
        k = N / span
        cen = (lo + hi) / 2
    else:
        k = N / units
        cen = np.zeros(2)
    color = np.zeros((N, N, 3), float)
    alpha = np.zeros((N, N), float)
    depth = np.full((N, N), -1e9)
    atlas = model.atlas.astype(float) / 255.0
    ys, xs = np.mgrid[0:N, 0:N] + 0.5
    for corners, n, (ax, ay, pw, ph), d, shade_on in faces:
        nn = R @ n
        if nn[2] <= 1e-6:
            continue
        P = [tr + R @ (scale * (p - 8.0)) for p in corners]
        scr = [np.array([(p[0] - cen[0]) * k + N / 2, N / 2 - (p[1] - cen[1]) * k]) for p in P]
        s00, s10, s01 = scr
        e1, e2 = s10 - s00, s01 - s00
        det = e1[0] * e2[1] - e1[1] * e2[0]
        if abs(det) < 1e-9:
            continue
        quad = np.array([s00, s10, s01, s10 + e2])
        x0, y0 = np.floor(quad.min(0)).astype(int)
        x1, y1 = np.ceil(quad.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, N), min(y1, N)
        if x0 >= x1 or y0 >= y1:
            continue
        px = xs[y0:y1, x0:x1] - s00[0]
        py = ys[y0:y1, x0:x1] - s00[1]
        a = (px * e2[1] - py * e2[0]) / det
        b = (e1[0] * py - e1[1] * px) / det
        inside = (a >= 0) & (a < 1) & (b >= 0) & (b < 1)
        if not inside.any():
            continue
        z = P[0][2] + a * (P[1][2] - P[0][2]) + b * (P[2][2] - P[0][2])
        tu = np.clip((ax + a * pw).astype(int), ax, ax + pw - 1)
        tv = np.clip((ay + b * ph).astype(int), ay, ay + ph - 1)
        tex = atlas[tv, tu]
        vis = inside & (tex[..., 3] > 0.1) & (z > depth[y0:y1, x0:x1])
        if not vis.any():
            continue
        sh = SHADE[d] if shade_on else 1.0
        sub_c = color[y0:y1, x0:x1]
        sub_c[vis] = tex[..., :3][vis] * sh
        alpha[y0:y1, x0:x1][vis] = 1.0
        depth[y0:y1, x0:x1][vis] = z[vis]
    img = np.zeros((N, N, 4), float)
    img[..., :3] = color
    img[..., 3] = alpha
    out = Image.fromarray((img * 255).astype(np.uint8), "RGBA")
    if ssaa > 1:
        out = out.resize((size, size), Image.LANCZOS)
    if bg[3] > 0:
        base = Image.new("RGBA", out.size, bg)
        base.alpha_composite(out)
        out = base
    return out


def slot_preview(model, zoom=8, bg=(139, 139, 139, 255)):
    """How the icon sits inside a 16x16 inventory slot (uses the model's gui display)."""
    g = model.display["gui"]
    img = render(model, rotation=g["rotation"], size=16 * zoom, fit=False, units=16, ssaa=4,
                 translation=g["translation"], scale=g["scale"][0], bg=(0, 0, 0, 0))
    base = Image.new("RGBA", img.size, bg)
    base.alpha_composite(img)
    return base


def sheet(images, cols, bg=(34, 36, 40, 255), pad=8):
    w = max(i.size[0] for i in images)
    h = max(i.size[1] for i in images)
    rows = (len(images) + cols - 1) // cols
    out = Image.new("RGBA", (cols * (w + pad) + pad, rows * (h + pad) + pad), bg)
    for n, im in enumerate(images):
        x = pad + (n % cols) * (w + pad)
        y = pad + (n // cols) * (h + pad)
        out.alpha_composite(im, (x, y))
    return out
