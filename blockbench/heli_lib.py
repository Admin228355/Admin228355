"""Общая библиотека генераторов Blockbench-моделей вертолётов.

Даёт: векторную математику, рисование текстуры, кубы/панели/лофт/трубы/диски,
группы и анимации Blockbench, запись .bbmodel и экспорт частей в ресурспак
Java 26.1.2 для Paper-плагина (paper-plugin/).
"""
import base64
import json
import math
import os
import random
import struct
import uuid
import zipfile
import zlib

LIB = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(LIB, "..", "paper-plugin")
PACK_DIR = os.path.join(PLUGIN, "resourcepack")
RNG = random.Random(1986)
TEX = 256
img = [[(0, 0, 0, 0) for _ in range(TEX)] for _ in range(TEX)]
MAT = {}
elements = []
FACE_AXES = {"north": (0, 1), "south": (0, 1), "east": (2, 1), "west": (2, 1), "up": (0, 2), "down": (0, 2)}
DENS = 2.0
I3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
JAVA_ROTATION_ORDER = "ZYX"
JAVA_SHRINK = 4
BLOCKS_PER_UNIT = 1 / 8

def new_uuid():
    return str(uuid.UUID(int=RNG.getrandbits(128), version=4))

def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)

def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

def length(a): return math.sqrt(dot(a, a))

def norm(a):
    n = length(a)
    return mul(a, 1 / n) if n > 1e-9 else (0, 0, 0)

def lerp(a, b, t): return a + (b - a) * t

def euler_zyx(X, Y, Z):
    """Матрица со столбцами X,Y,Z -> углы Эйлера (градусы) в порядке ZYX (как в Blockbench)."""
    m31, m32, m33, m21, m11 = X[2], Y[2], Z[2], X[1], X[0]
    y = math.asin(max(-1, min(1, -m31)))
    if abs(m31) < 0.9999999:
        x = math.atan2(m32, m33)
        z = math.atan2(m21, m11)
    else:
        x = 0
        z = math.atan2(-Y[0], Y[1])
    return [round(math.degrees(v), 4) for v in (x, y, z)]

def clamp(v):
    return max(0, min(255, int(round(v))))

def put(x, y, c, a=255):
    if 0 <= x < TEX and 0 <= y < TEX:
        img[y][x] = (clamp(c[0]), clamp(c[1]), clamp(c[2]), clamp(a))

def get(x, y):
    return img[y][x]

def shade(c, k): return (c[0] * k, c[1] * k, c[2] * k)

def mix(a, b, t): return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

def noisy(c, amp):
    n = RNG.uniform(-amp, amp)
    return (c[0] + n, c[1] + n * 1.04, c[2] + n * 0.85)

def _h(ix, iy, s):
    return ((ix * 374761393 + iy * 668265263 + s * 982451653) & 0xFFFFFFFF) / 0xFFFFFFFF

def vnoise(x, y, s=0):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = lerp(_h(ix, iy, s), _h(ix + 1, iy, s), fx)
    b = lerp(_h(ix, iy + 1, s), _h(ix + 1, iy + 1, s), fx)
    return lerp(a, b, fy)

def fbm(x, y, s=0, oct=4):
    v, amp, tot = 0, 1, 0
    for o in range(oct):
        v += vnoise(x, y, s + o * 17) * amp
        tot += amp
        x, y, amp = x * 2.03, y * 2.03, amp * 0.5
    return v / tot

def fill(x0, y0, w, h, fn):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            r = fn(x - x0, y - y0)
            put(x, y, r[:3], r[3] if len(r) == 4 else 255)

def tile(name, u, v, w, h, whole, fn):
    MAT[name] = (u, v, w, h, whole)
    fill(u, v, w, h, fn)

def in_poly(x, y, pts):
    ins = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi:
            ins = not ins
        j = i
    return ins

def face_uv(mat, size, face):
    u, v, w, h, whole = MAT[mat]
    if whole:
        return [u, v, u + w, v + h]
    au, av = FACE_AXES[face]
    fw = max(0.5, min(w, size[au] * DENS))
    fh = max(0.5, min(h, size[av] * DENS))
    ou, ov = RNG.uniform(0, w - fw), RNG.uniform(0, h - fh)
    q = lambda n: round(n * 4) / 4
    return [q(u + ou), q(v + ov), q(u + ou + fw), q(v + ov + fh)]

def make_el(name, frm, to, faces, origin, rot):
    size = [t - f for f, t in zip(frm, to)]
    fdict = {}
    for f in ("north", "east", "south", "west", "up", "down"):
        spec = faces[f]
        uv = spec if isinstance(spec, list) else face_uv(spec, size, f)
        fdict[f] = {"uv": [round(x, 3) for x in uv], "texture": 0}
    el = {"name": name, "box_uv": False, "rescale": False, "locked": False,
          "render_order": "default", "allow_mirror_modeling": True,
          "from": [round(x, 4) for x in frm], "to": [round(x, 4) for x in to],
          "autouv": 0, "color": RNG.randrange(8), "origin": [round(x, 4) for x in origin],
          "faces": fdict, "type": "cube", "uuid": new_uuid()}
    if rot and any(abs(r) > 1e-4 for r in rot):
        el["rotation"] = rot
    elements.append(el)
    return el["uuid"]

def cube(name, frm, to, mat="hull", faces=None, origin=None, rot=None):
    faces = faces or {}
    a = [min(p, q) for p, q in zip(frm, to)]
    b = [max(p, q) for p, q in zip(frm, to)]
    fs = {f: faces.get(f, mat) for f in FACE_AXES}
    return make_el(name, a, b, fs, origin or [(p + q) / 2 for p, q in zip(a, b)], rot)

def ocube(name, O, X, Y, Z, lo, hi, faces):
    """Куб в локальном базисе (X,Y,Z) с началом O; lo/hi — локальные границы."""
    frm = [O[i] + lo[i] for i in range(3)]
    to = [O[i] + hi[i] for i in range(3)]
    return make_el(name, frm, to, faces, list(O), euler_zyx(X, Y, Z))

def basis_from(dirz, hint=(0, 1, 0)):
    Z = norm(dirz)
    if abs(dot(Z, norm(hint))) > 0.95:
        hint = (1, 0, 0)
    X = norm(cross(hint, Z))
    Y = cross(Z, X)
    return X, Y, Z

def rod(name, p0, p1, r, mat="metal"):
    """Стержень из двух квадратных кубов, повёрнутых на 45° — восьмигранник."""
    X, Y, Z = basis_from(sub(p1, p0))
    L = length(sub(p1, p0))
    O = mul(add(p0, p1), 0.5)
    s = r * 0.924
    out = []
    for k, ang in enumerate((0, 45)):
        a = math.radians(ang)
        Xa = add(mul(X, math.cos(a)), mul(Y, math.sin(a)))
        Ya = cross(Z, Xa)
        out.append(ocube(f"{name}_{k}", O, Xa, Ya, Z, (-s, -s, -L / 2), (s, s, L / 2),
                         {f: mat for f in FACE_AXES}))
    return out

def disc(name, C, normal, r, t, mat="metal", face_mat=None, n=6):
    """Круглый диск из n тонких прямоугольников, повёрнутых вокруг нормали
    (объединение даёт почти идеальный 4n-угольник без торчащих углов)."""
    X, Y, Z = basis_from(normal)
    hw = r * math.tan(math.pi / (2 * n))
    out = []
    fm = face_mat or mat
    for k in range(n):
        a = math.pi * k / n
        Xa = add(mul(X, math.cos(a)), mul(Y, math.sin(a)))
        Ya = cross(Z, Xa)
        out.append(ocube(f"{name}_{k}", C, Xa, Ya, Z, (-r, -hw, -t / 2), (r, hw, t / 2),
                         {"north": fm, "south": fm, "east": mat, "west": mat, "up": mat, "down": mat}))
    return out

def panel(name, p0, p1, p2, p3, ref, t, outer, inner="wall", edge="hull"):
    """Панель обшивки по четырёхугольнику p0-p1 (одно сечение), p3-p2 (следующее).
    Внешняя грань (up) лежит на поверхности, толщина уходит внутрь.
    outer: имя материала или uv-прямоугольник [u0,v0,u1,v1] (u вдоль p0->p1, v вдоль p0->p3)."""
    u = mul(add(sub(p1, p0), sub(p2, p3)), 0.5)
    v = mul(add(sub(p3, p0), sub(p2, p1)), 0.5)
    if length(u) < 0.03 or length(v) < 0.03:
        return None
    c = mul(add(add(p0, p1), add(p2, p3)), 0.25)
    X = norm(u)
    Z = norm(sub(v, mul(X, dot(v, X))))
    Y = cross(Z, X)
    flipped = False
    if dot(Y, sub(c, ref)) < 0:
        X, Y, flipped = mul(X, -1), mul(Y, -1), True
    w = length(u) * 1.03 + 0.06
    L = dot(v, Z) + 0.12
    if isinstance(outer, list) and flipped:
        outer = [outer[2], outer[1], outer[0], outer[3]]
    return ocube(name, c, X, Y, Z, (-w / 2, -t, -L / 2), (w / 2, 0, L / 2),
                 {"up": outer, "down": inner, "north": edge, "south": edge, "east": edge, "west": edge})

def loft(name, rings, centers, t, outer_fn, dest_fn, closed=True, inner="wall", edge="hull"):
    """rings[i] — список точек сечения i. outer_fn(i,k,c) -> материал или uv.
    dest_fn(i,k,c) -> список, куда положить uuid (или None — пропустить)."""
    n = len(rings[0])
    segs = n if closed else n - 1
    for i in range(len(rings) - 1):
        ref = mul(add(centers[i], centers[i + 1]), 0.5)
        for k in range(segs):
            k1 = (k + 1) % n
            p0, p1, p2, p3 = rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]
            c = mul(add(add(p0, p1), add(p2, p3)), 0.25)
            dest = dest_fn(i, k, c)
            if dest is None:
                continue
            inn = inner(i, k, c) if callable(inner) else inner
            uid = panel(f"{name}_{i}_{k}", p0, p1, p2, p3, ref, t, outer_fn(i, k, c), inn, edge)
            if uid:
                dest.append(uid)

def ring_frame(C, T, ref):
    e1 = norm(sub(ref, mul(T, dot(ref, T))))
    e2 = cross(T, e1)
    return e1, e2

def tube(name, path, radii, n, dest, outer="hull", inner="soot", t=0.35, ref=(0, 1, 0), edge="hull"):
    """Труба по ломаной path; radii — (r1, r2) по осям e1/e2 на каждую точку."""
    rings, centers = [], []
    for i, C in enumerate(path):
        if i == 0:
            T = sub(path[1], path[0])
        elif i == len(path) - 1:
            T = sub(path[-1], path[-2])
        else:
            T = add(norm(sub(path[i], path[i - 1])), norm(sub(path[i + 1], path[i])))
        T = norm(T)
        e1, e2 = ring_frame(C, T, ref)
        r1, r2 = radii[i] if isinstance(radii[i], tuple) else (radii[i], radii[i])
        rings.append([add(C, add(mul(e1, r1 * math.cos(2 * math.pi * k / n)),
                                 mul(e2, r2 * math.sin(2 * math.pi * k / n)))) for k in range(n)])
        centers.append(C)
    loft(name, rings, centers, t, lambda i, k, c: outer, lambda i, k, c: dest, inner=inner, edge=edge)

def group(name, origin, children, rotation=None):
    g = {"name": name, "origin": [round(x, 4) for x in origin], "color": 0, "uuid": new_uuid(), "export": True,
         "mirror_uv": False, "isOpen": False, "locked": False, "visibility": True,
         "autouv": 0, "children": children}
    if rotation:
        g["rotation"] = rotation
    return g

def pchip(xs, ys):
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = max(j for j in range(n - 1) if xs[j] <= x)
        t = (x - xs[i]) / h[i]
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]
    return f

def kf(channel, t, xyz, interp="linear"):
    return {"channel": channel, "data_points": [{"x": str(round(xyz[0], 3)), "y": str(round(xyz[1], 3)),
                                                  "z": str(round(xyz[2], 3))}],
            "uuid": new_uuid(), "time": round(t, 4), "color": -1, "interpolation": interp}

def spin(axis, length, turns):
    v = lambda a: tuple(a if i == axis else 0 for i in range(3))
    return [(0, v(0)), (length, v(360 * turns))]

def ramp_spin(axis, t0, t1, max_dps, speed_up=True, step=0.25):
    pts, dur = [], t1 - t0
    a = max_dps / dur
    for i in range(int(round(dur / step)) + 1):
        t = i * step
        ang = 0.5 * a * t * t if speed_up else max_dps * t - 0.5 * a * t * t
        pts.append((t0 + t, tuple(ang if j == axis else 0 for j in range(3))))
    return pts

def wave(axes, length, n, phase=0.0, base=(0, 0, 0)):
    pts = []
    for i in range(n + 1):
        t = length * i / n
        v = list(base)
        for axis, amp, fm in axes:
            v[axis] += amp * math.sin(2 * math.pi * fm * t / length + phase)
        pts.append((t, tuple(v), "catmullrom"))
    return pts

def mat_mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def mat_vec(A, v):
    return tuple(sum(A[i][k] * v[k] for k in range(3)) for i in range(3))

def rot_zyx(r):
    x, y, z = (math.radians(a) for a in r)
    Rx = [[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]]
    Ry = [[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]]
    Rz = [[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]]
    return mat_mul(Rz, mat_mul(Ry, Rx))

def collect(node, Ra, ta, out, skip):
    """Собирает элементы группы с учётом поворотов вложенных групп."""
    if node.get("rotation"):
        G = node["origin"]
        Rg = rot_zyx(node["rotation"])
        # A(p) = Ra*(G + Rg*(p-G)) + ta
        tg = sub(tuple(G), mat_vec(Rg, tuple(G)))
        ta = add(mat_vec(Ra, tg), ta)
        Ra = mat_mul(Ra, Rg)
    for c in node["children"]:
        if isinstance(c, str):
            out.append((ELS[c], Ra, ta))
        elif c["name"] not in skip:
            collect(c, Ra, ta, out, skip)

def euler_xyz(R):
    """R = Rx*Ry*Rz -> углы (x, y, z) в градусах."""
    y = math.asin(max(-1, min(1, R[0][2])))
    if abs(R[0][2]) < 0.9999999:
        x = math.atan2(-R[1][2], R[2][2])
        z = math.atan2(-R[0][1], R[0][0])
    else:
        x, z = math.atan2(R[2][1], R[1][1]), 0
    return [round(math.degrees(v), 4) for v in (x, y, z)]


def animation(name, length, loop, tracks, groups):
    animators = {}
    for bone, chans in tracks.items():
        g = groups[bone]
        keys = []
        for ch, pts in chans.items():
            for p in pts:
                keys.append(kf(ch, p[0], p[1], p[2] if len(p) > 2 else "linear"))
        animators[g["uuid"]] = {"name": bone, "type": "bone", "keyframes": keys}
    return {"uuid": new_uuid(), "name": name, "loop": loop, "override": False, "length": length,
            "snapping": 20, "selected": False, "anim_time_update": "", "blend_weight": "",
            "start_delay": "", "loop_delay": "", "animators": animators}


def index_groups(root):
    out = {}

    def walk(g):
        out[g["name"]] = g
        for c in g["children"]:
            if isinstance(c, dict):
                walk(c)
    walk(root)
    return out


def png_bytes():
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in img)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", TEX, TEX, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def write_bbmodel(path, name, root, anims, tex_png, tex_name):
    model = {
        "meta": {"format_version": "4.10", "model_format": "free", "box_uv": False},
        "name": name, "model_identifier": name, "visible_box": [10, 6, 1],
        "variable_placeholders": "", "variable_placeholder_buttons": [], "timeline_setups": [],
        "unhandled_root_fields": {}, "resolution": {"width": TEX, "height": TEX},
        "elements": elements, "outliner": [root],
        "textures": [{
            "path": "", "name": tex_name, "folder": "", "namespace": "", "id": "0",
            "group": "", "width": TEX, "height": TEX, "uv_width": TEX, "uv_height": TEX,
            "particle": False, "use_as_default": True, "layers_enabled": False, "sync_to_project": "",
            "render_mode": "default", "render_sides": "auto", "pbr_channel": "color",
            "frame_time": 1, "frame_order_type": "loop", "frame_order": "", "frame_interpolate": False,
            "visible": True, "internal": True, "saved": False, "uuid": new_uuid(), "relative_path": "",
            "source": "data:image/png;base64," + base64.b64encode(tex_png).decode(),
        }],
        "animations": anims,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, separators=(",", ":"))


def java_element(e, Ra, ta, pivot):
    O = tuple(e["origin"])
    Re = rot_zyx(e.get("rotation", [0, 0, 0]))
    O2 = add(mat_vec(Ra, O), ta)
    R2 = mat_mul(Ra, Re)
    X = (R2[0][0], R2[1][0], R2[2][0])
    Y = (R2[0][1], R2[1][1], R2[2][1])
    Z = (R2[0][2], R2[1][2], R2[2][2])
    ang = euler_zyx(X, Y, Z) if JAVA_ROTATION_ORDER == "ZYX" else euler_xyz(R2)
    k = 1 / JAVA_SHRINK
    o = [round((O2[i] - pivot[i]) * k + 8, 4) for i in range(3)]
    frm = [round(o[i] + (e["from"][i] - O[i]) * k, 4) for i in range(3)]
    to = [round(o[i] + (e["to"][i] - O[i]) * k, 4) for i in range(3)]
    for v in frm + to:
        assert -16 <= v <= 32, (e["name"], frm, to)
    je = {"from": frm, "to": to, "faces": {}}
    nz = [(i, a) for i, a in enumerate(ang) if abs(a) > 1e-3]
    if nz:
        if len(nz) == 1 and any(abs(nz[0][1] - s) < 1e-3 for s in (-45, -22.5, 22.5, 45)):
            je["rotation"] = {"origin": o, "axis": "xyz"[nz[0][0]], "angle": round(nz[0][1], 3)}
        else:
            je["rotation"] = {"origin": o, "x": ang[0], "y": ang[1], "z": ang[2]}
    for f, fd in e["faces"].items():
        je["faces"][f] = {"uv": [round(u * 16 / TEX, 4) for u in fd["uv"]], "texture": "#0"}
    return je


def export_parts(type_id, root, groups, parts, tex_png):
    """parts: [(ключ, группа|None, pivot|None, доп.поля для плагина)].
    Пишет модели в paper-plugin/resourcepack и возвращает описания частей (pivot в блоках)."""
    els = {e["uuid"]: e for e in elements}
    moved = {g for _, g, _, _ in parts if g}
    out = []
    for key, gname, pivot, extra in parts:
        items = []

        def collect2(node, Ra, ta, skip):
            if node.get("rotation"):
                G = node["origin"]
                Rg = rot_zyx(node["rotation"])
                tg = sub(tuple(G), mat_vec(Rg, tuple(G)))
                ta = add(mat_vec(Ra, tg), ta)
                Ra = mat_mul(Ra, Rg)
            for c in node["children"]:
                if isinstance(c, str):
                    items.append((els[c], Ra, ta))
                elif c["name"] not in skip:
                    collect2(c, Ra, ta, skip)
        if gname:
            pivot = tuple(groups[gname]["origin"])
            collect2(groups[gname], I3, (0, 0, 0), set())
        else:
            collect2(root, I3, (0, 0, 0), moved)
        model = {"textures": {"0": f"heli:item/{type_id}", "particle": f"heli:item/{type_id}"},
                 "elements": [java_element(e, Ra, ta, pivot) for e, Ra, ta in items]}
        write_pack_file(f"assets/heli/models/item/{key}.json", json.dumps(model, separators=(",", ":")))
        write_pack_file(f"assets/heli/items/{key}.json",
                        json.dumps({"model": {"type": "minecraft:model", "model": f"heli:item/{key}"}}))
        d = {"key": key, "pivot": [round(c * BLOCKS_PER_UNIT, 5) for c in pivot]}
        d.update(extra or {})
        out.append(d)
    write_pack_file(f"assets/heli/textures/item/{type_id}.png", tex_png)
    return out


def write_pack_file(rel, data):
    path = os.path.join(PACK_DIR, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data.encode("utf-8") if isinstance(data, str) else data)


def write_type(type_id, spec):
    """Описание типа вертолёта для плагина (JSON — валидный YAML)."""
    d = os.path.join(PLUGIN, "src", "main", "resources", "types")
    os.makedirs(d, exist_ok=True)
    spec = dict(spec, **{"id": type_id, "blocks-per-unit": BLOCKS_PER_UNIT,
                         "display-scale": JAVA_SHRINK * 16 * BLOCKS_PER_UNIT})
    with open(os.path.join(d, f"{type_id}.yml"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    ids = sorted(n[:-4] for n in os.listdir(d) if n.endswith(".yml") and n != "index.yml")
    with open(os.path.join(d, "index.yml"), "w", encoding="utf-8") as f:
        json.dump({"types": ids}, f)
    build_pack()


def build_pack():
    """Собирает paper-plugin/resourcepack/ в src/main/resources/heli_resourcepack.zip."""
    write_pack_file("pack.mcmeta", json.dumps({"pack": {
        "description": "Helicopters (heli plugin)", "min_format": 69, "max_format": 999}}, indent=2))
    zpath = os.path.join(PLUGIN, "src", "main", "resources", "heli_resourcepack.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in sorted(os.walk(PACK_DIR)):
            for n in sorted(files):
                full = os.path.join(base, n)
                rel = os.path.relpath(full, PACK_DIR).replace(os.sep, "/")
                zi = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                with open(full, "rb") as fh:
                    z.writestr(zi, fh.read())
    print("resource pack:", os.path.relpath(zpath, LIB), f"{os.path.getsize(zpath) // 1024} KB")

