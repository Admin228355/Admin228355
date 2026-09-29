"""Core of the furniture generator: boxes -> Java Block/Item model JSON + texture atlas.

Target: Minecraft Java 1.16.5 (resource pack format 6).
  * element coordinates must stay inside [-16, 32]
  * element rotation: one axis, angle in {-45, -22.5, 0, 22.5, 45}
  * UVs are written in the 0..16 space, "texture_size" is only a Blockbench hint
"""
import json
import math
import os

import numpy as np
from PIL import Image

DIRS = ("north", "south", "west", "east", "up", "down")
NORMAL = {
    "north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0),
    "east": (1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0),
}
AXIS_OF = {"north": "z", "south": "z", "west": "x", "east": "x", "up": "y", "down": "y"}
ALLOWED_ANGLES = (-45.0, -22.5, 0.0, 22.5, 45.0)


def face_corners(frm, to, d):
    """P00 (uv u1,v1), P10 (u2,v1), P01 (u1,v2) -- same orientation vanilla uses for default UVs."""
    x1, y1, z1 = frm
    x2, y2, z2 = to
    return {
        "north": ((x2, y2, z1), (x1, y2, z1), (x2, y1, z1)),
        "south": ((x1, y2, z2), (x2, y2, z2), (x1, y1, z2)),
        "west": ((x1, y2, z1), (x1, y2, z2), (x1, y1, z1)),
        "east": ((x2, y2, z2), (x2, y2, z1), (x2, y1, z2)),
        "up": ((x1, y2, z1), (x2, y2, z1), (x1, y2, z2)),
        "down": ((x1, y1, z2), (x2, y1, z2), (x1, y1, z1)),
    }[d]


class FaceCtx:
    """Everything a painter needs to know about one face (per-texel world coordinates etc.)."""

    def __init__(self, el, d, pw, ph, dens):
        p00, p10, p01 = (np.array(p, dtype=float) for p in face_corners(el.frm, el.to, d))
        self.el, self.dir, self.pw, self.ph, self.dens = el, d, pw, ph, dens
        self.axis = AXIS_OF[d]
        self.W = float(np.linalg.norm(p10 - p00))
        self.H = float(np.linalg.norm(p01 - p00))
        i = (np.arange(pw) + 0.5) / pw
        j = (np.arange(ph) + 0.5) / ph
        I, J = np.meshgrid(i, j)
        P = p00 + I[..., None] * (p10 - p00) + J[..., None] * (p01 - p00)
        self.X, self.Y, self.Z = P[..., 0], P[..., 1], P[..., 2]
        self.fu, self.fv = I * self.W, J * self.H  # face-local units, from the top-left corner
        self.ii, self.jj = np.meshgrid(np.arange(pw), np.arange(ph))  # integer texel indices
        self.seed = el.seed

    def coord(self, a):
        return {"x": self.X, "y": self.Y, "z": self.Z}[a]


class Element:
    def __init__(self, name, frm, to, paint, skip=(), over=None, rot=None, share=None, seed=0, shade=True):
        self.name, self.frm, self.to = name, tuple(frm), tuple(to)
        self.rot = rot  # (axis, angle, origin)
        self.shade = shade
        self.seed = seed
        over = over or {}
        share = share or {}
        self.faces = {}
        for d in DIRS:
            if d in skip:
                continue
            self.faces[d] = {"paint": over.get(d, paint), "share": share.get(d)}


class Model:
    def __init__(self, name, dens=4, namespace="zona_item", folder="item"):
        self.name, self.dens, self.ns, self.folder = name, dens, namespace, folder
        self.elements = []
        self.display = {}

    def box(self, name, frm, to, paint, **kw):
        kw.setdefault("seed", (len(self.elements) * 7919 + sum(map(ord, name)) * 31) % 100003)
        el = Element(name, frm, to, paint, **kw)
        self.elements.append(el)
        return el

    # ------------------------------------------------------------------ atlas
    def _pack(self, rects, gutter=1):
        order = sorted(rects, key=lambda r: (-r["ph"], -r["pw"]))
        for S in (32, 64, 128, 256, 512, 1024, 2048):
            x = y = shelf = 0
            ok = True
            for r in order:
                if r["pw"] > S:
                    ok = False
                    break
                if x + r["pw"] > S:
                    x, y, shelf = 0, y + shelf + gutter, 0
                if y + r["ph"] > S:
                    ok = False
                    break
                r["ax"], r["ay"] = x, y
                x += r["pw"] + gutter
                shelf = max(shelf, r["ph"])
            if ok:
                return S
        raise RuntimeError("atlas too large")

    def build(self):
        rects, by_share = [], {}
        for el in self.elements:
            for d, f in el.faces.items():
                p00, p10, p01 = (np.array(p, float) for p in face_corners(el.frm, el.to, d))
                W = np.linalg.norm(p10 - p00)
                H = np.linalg.norm(p01 - p00)
                pw = max(1, int(round(W * self.dens)))
                ph = max(1, int(round(H * self.dens)))
                key = f["share"]
                if key and key in by_share:
                    f["rect"] = by_share[key]
                    continue
                r = {"el": el, "dir": d, "pw": pw, "ph": ph, "paint": f["paint"]}
                rects.append(r)
                f["rect"] = r
                if key:
                    by_share[key] = r
        S = self._pack(rects)
        img = np.zeros((S, S, 4), np.uint8)
        occ = np.zeros((S, S), bool)
        for r in rects:
            ctx = FaceCtx(r["el"], r["dir"], r["pw"], r["ph"], self.dens)
            px = r["paint"](ctx)
            assert px.shape == (r["ph"], r["pw"], 4), (r["el"].name, r["dir"], px.shape)
            img[r["ay"]:r["ay"] + r["ph"], r["ax"]:r["ax"] + r["pw"]] = px
            occ[r["ay"]:r["ay"] + r["ph"], r["ax"]:r["ax"] + r["pw"]] = True
        img = _dilate_gutters(img, occ, steps=1)
        self.atlas, self.S = img, S
        return img

    # ------------------------------------------------------------------ json
    def to_json(self):
        S = self.S
        tex = f"{self.ns}:{self.folder}/{self.name}"
        els = []
        for el in self.elements:
            faces = {}
            for d in DIRS:
                if d not in el.faces:
                    continue
                r = el.faces[d]["rect"]
                uv = [r["ax"] * 16 / S, r["ay"] * 16 / S, (r["ax"] + r["pw"]) * 16 / S, (r["ay"] + r["ph"]) * 16 / S]
                faces[d] = {"uv": [_num(v) for v in uv], "texture": "#0"}
            e = {"name": el.name, "from": [_num(v) for v in el.frm], "to": [_num(v) for v in el.to]}
            if not el.shade:
                e["shade"] = False
            if el.rot:
                axis, angle, origin = el.rot
                e["rotation"] = {"angle": _num(angle), "axis": axis, "origin": [_num(v) for v in origin]}
            e["faces"] = faces
            els.append(e)
        return {
            "texture_size": [S, S],
            "textures": {"0": tex, "particle": tex},
            "elements": els,
            "gui_light": "side",
            "display": self.display,
        }

    def write(self, pack_root):
        tdir = os.path.join(pack_root, "assets", self.ns, "textures", self.folder)
        mdir = os.path.join(pack_root, "assets", self.ns, "models", self.folder)
        os.makedirs(tdir, exist_ok=True)
        os.makedirs(mdir, exist_ok=True)
        Image.fromarray(self.atlas, "RGBA").save(os.path.join(tdir, self.name + ".png"), optimize=True)
        data = self.to_json()
        validate(data, self.name)
        with open(os.path.join(mdir, self.name + ".json"), "w", encoding="utf-8") as fh:
            fh.write(dump_model(data))
        return data

    # ------------------------------------------------------------------ display
    def corners(self):
        pts = []
        for el in self.elements:
            x1, y1, z1 = el.frm
            x2, y2, z2 = el.to
            for x in (x1, x2):
                for y in (y1, y2):
                    for z in (z1, z2):
                        pts.append(rotate_point((x, y, z), el.rot))
        return np.array(pts)

    def auto_display(self, gui_rot=(25, 205, 0), head=True, fixed="floor", margin=0.98):
        pts = self.corners() - 8.0
        # size of a vanilla full block in the slot = reference for "fills the slot"
        cube = np.array([[x, y, z] for x in (-8, 8) for y in (-8, 8) for z in (-8, 8)], float)
        cp = cube @ euler(30, 225, 0).T * 0.625
        tw, th = np.ptp(cp[:, 0]), np.ptp(cp[:, 1])
        p = pts @ euler(*gui_rot).T
        w, h = np.ptp(p[:, 0]), np.ptp(p[:, 1])
        s = min(tw / w, th / h) * margin
        c = (p.max(0) + p.min(0)) / 2 * s
        dim = max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1]), np.ptp(pts[:, 2]))
        k = 16.0 / max(dim, 16.0)
        disp = {
            "gui": {"rotation": list(gui_rot), "translation": [_num(-c[0], 2), _num(-c[1], 2), 0], "scale": [_num(s, 4)] * 3},
            "ground": {"rotation": [0, 0, 0], "translation": [0, 3, 0], "scale": [_num(0.25 * k, 4)] * 3},
            "thirdperson_righthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [_num(0.375 * k, 4)] * 3},
            "thirdperson_lefthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [_num(0.375 * k, 4)] * 3},
            "firstperson_righthand": {"rotation": [0, 45, 0], "translation": [0, 0, 0], "scale": [_num(0.4 * k, 4)] * 3},
            "firstperson_lefthand": {"rotation": [0, 225, 0], "translation": [0, 0, 0], "scale": [_num(0.4 * k, 4)] * 3},
        }
        if head:
            # armor stand head slot -> model at 1:1 world scale standing on the stand's feet
            disp["head"] = {"rotation": [0, 0, 0], "translation": [0, -30.43, 0], "scale": [1.6, 1.6, 1.6]}
        if fixed == "floor":
            # invisible item frame lying on the floor (Oraxen-style furniture) -> 1:1 world scale
            disp["fixed"] = {"rotation": [-90, 0, 0], "translation": [0, 0, -16], "scale": [2, 2, 2]}
        self.display = disp
        return disp


# ---------------------------------------------------------------------- helpers
def _num(v, nd=4):
    v = round(float(v), nd)
    if v == int(v):
        return int(v)
    return v


def _dilate_gutters(img, occ, steps=1):
    """Copies border texels of every face into the empty gutter around it (no mip-map seams)."""
    img = img.copy()
    filled = occ.copy()
    H, W = filled.shape
    for _ in range(steps):
        new, nf = img.copy(), filled.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.zeros_like(img)
            sf = np.zeros_like(filled)
            ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
            xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
            src[yd, xd] = img[ys, xs]
            sf[yd, xd] = filled[ys, xs]
            m = (~nf) & sf
            new[m] = src[m]
            nf |= m
        img, filled = new, nf
    return img


def euler(rx, ry, rz):
    """Rotation matrix exactly like Minecraft's Quaternion(x, y, z, degrees): R = Rx * Ry * Rz."""
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    Rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return Rx @ Ry @ Rz


def axis_rot(axis, angle):
    return euler(*(angle if a == axis else 0 for a in "xyz"))


def rotate_point(p, rot):
    if not rot:
        return np.array(p, float)
    axis, angle, origin = rot
    o = np.array(origin, float)
    return axis_rot(axis, angle) @ (np.array(p, float) - o) + o


def dump_model(data):
    """Blockbench-like layout: one element per line, readable and diff-friendly."""
    out = ["{"]
    keys = list(data.keys())
    for n, k in enumerate(keys):
        comma = "," if n < len(keys) - 1 else ""
        v = data[k]
        if k == "elements":
            out.append('\t"elements": [')
            for i, e in enumerate(v):
                out.append("\t\t" + json.dumps(e, ensure_ascii=False, separators=(", ", ": ")) + ("," if i < len(v) - 1 else ""))
            out.append("\t]" + comma)
        elif k == "display":
            out.append('\t"display": {')
            dk = list(v.keys())
            for i, name in enumerate(dk):
                out.append(f'\t\t"{name}": ' + json.dumps(v[name], separators=(", ", ": ")) + ("," if i < len(dk) - 1 else ""))
            out.append("\t}" + comma)
        else:
            out.append(f'\t"{k}": ' + json.dumps(v, ensure_ascii=False, separators=(", ", ": ")) + comma)
    out.append("}")
    return "\n".join(out) + "\n"


def validate(data, name=""):
    """Checks the rules the 1.16.5 model loader enforces (and a few that silently break models)."""
    errs = []
    for i, e in enumerate(data["elements"]):
        tag = f"{name}#{i}:{e.get('name')}"
        for v in e["from"] + e["to"]:
            if not -16 <= v <= 32:
                errs.append(f"{tag}: coordinate {v} outside [-16, 32]")
        for a in range(3):
            if e["from"][a] > e["to"][a]:
                errs.append(f"{tag}: from > to on axis {a}")
        r = e.get("rotation")
        if r:
            if r["axis"] not in ("x", "y", "z"):
                errs.append(f"{tag}: bad axis")
            if float(r["angle"]) not in ALLOWED_ANGLES:
                errs.append(f"{tag}: angle {r['angle']} not allowed in 1.16.5")
        if not e["faces"]:
            errs.append(f"{tag}: no faces")
        for d, f in e["faces"].items():
            if d not in DIRS:
                errs.append(f"{tag}: bad face {d}")
            if any(not 0 <= u <= 16 for u in f["uv"]):
                errs.append(f"{tag}: uv outside 0..16")
            if f["texture"].lstrip("#") not in data["textures"]:
                errs.append(f"{tag}: unknown texture {f['texture']}")
    for slot, t in data.get("display", {}).items():
        if any(abs(v) > 80 for v in t.get("translation", [0, 0, 0])):
            errs.append(f"{name}: display {slot} translation clamped (>80)")
        if any(abs(v) > 4 for v in t.get("scale", [1, 1, 1])):
            errs.append(f"{name}: display {slot} scale clamped (>4)")
    if errs:
        raise ValueError("\n".join(errs))
    return True
