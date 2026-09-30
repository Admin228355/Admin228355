#!/usr/bin/env python3
"""Генератор Blockbench-модели вертолёта «Ми-8» (зона отчуждения), версия 2 — сглаженная.

Корпус, мотогондола, хвостовая балка, баки, выхлопные трубы, колёса и киль
собираются «лофтом»: по набору сечений (суперэллипсов) строится обшивка из
тонких панелей, каждая панель — куб, повёрнутый по всем трём осям.
Поэтому модель получается гладкой, а не «кубической».

Создаёт:
  mi8_helicopter.bbmodel  — проект Blockbench (Generic Model), текстура 256x256
                            встроена, группы (кости) и анимации;
  mi8_texture.png         — та же текстура отдельным файлом.

Зависимостей нет (только стандартная библиотека Python 3).
Запуск:  python3 generate.py
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

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(HERE, "..", "..", "paper-plugin")
RNG = random.Random(1986)
TEX = 256


def new_uuid():
    return str(uuid.UUID(int=RNG.getrandbits(128), version=4))


# ---------------------------------------------------------------------------
# Векторы
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Текстура 256x256
# ---------------------------------------------------------------------------
img = [[(0, 0, 0, 0) for _ in range(TEX)] for _ in range(TEX)]


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


_P = list(range(512))
random.Random(7).shuffle(_P)


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


OLIVE = (82, 90, 54)
OLIVE_D = (60, 67, 40)
OLIVE_B = (92, 86, 56)
RUST = (116, 66, 34)
RUST_L = (152, 90, 44)
DARKM = (54, 56, 54)
GLASS = (52, 70, 78)
RED = (165, 36, 30)
WHITE = (206, 204, 190)


def camo_color(s, t, seed=0):
    """Камуфляж + износ по координатам s,t (в «мировых» единицах)."""
    n = fbm(s * 0.06, t * 0.06, seed)
    c = OLIVE if n < 0.53 else OLIVE_D
    if 0.47 < n < 0.5:
        c = OLIVE_B
    c = noisy(c, 5)
    g = fbm(s * 0.35, t * 0.35, seed + 5)
    c = shade(c, 0.9 + g * 0.2)
    r = fbm(s * 0.22, t * 0.22, seed + 9)
    if r > 0.7:
        c = mix(c, RUST if r < 0.75 else RUST_L, min(0.85, (r - 0.7) * 8))
    return c


# --- тайлы материалов (нижняя половина атласа) ---
MAT = {}  # имя: (u, v, w, h, растягивать_целиком)


def tile(name, u, v, w, h, whole, fn):
    MAT[name] = (u, v, w, h, whole)
    fill(u, v, w, h, fn)


def glass_px(x, y):
    c = noisy((70, 92, 102), 3)
    if 6 <= (x + y) % 23 <= 8:
        c = mix(c, (180, 200, 206), 0.4)
    d = fbm(x * 0.3, y * 0.3, 44)
    a = 165
    if d > 0.72:
        c, a = mix(c, (96, 88, 64), 0.35), 200
    return c + (a,)


tile("glass", 0, 128, 32, 32, False, glass_px)


def porthole_px(x, y):
    d = math.hypot(x - 7.5, y - 7.5)
    if d > 7.6:
        return (0, 0, 0, 0)
    if d > 6.4:
        return noisy((70, 76, 50), 4)
    if d > 5.3:
        return noisy((30, 31, 29), 3)
    c = noisy(GLASS, 4)
    if -2 <= x - y <= 0:
        c = mix(c, (170, 190, 196), 0.5)
    return c + (235,)


tile("porthole", 32, 128, 16, 16, True, porthole_px)


def star_poly(cx, cy, R, r):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


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


_SO, _SI = star_poly(15.5, 16.5, 15.5, 6.2), star_poly(15.5, 16.5, 13.2, 5.2)


def star_px(x, y):
    px, py = x + 0.5, y + 0.5
    if in_poly(px, py, _SI):
        c = noisy(RED, 10)
        if fbm(x * 0.4, y * 0.4, 3) > 0.7:
            c = mix(c, OLIVE, 0.6)
        return c
    if in_poly(px, py, _SO):
        return noisy(WHITE, 10) if fbm(x * 0.5, y * 0.5, 4) < 0.72 else noisy(OLIVE, 6)
    return (0, 0, 0, 0)


tile("star", 48, 128, 32, 32, True, star_px)

DIG = {
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
}


def number_px(x, y):
    for i, d in enumerate("32"):
        gx, gy = (x - 4 - i * 13) // 2, (y - 1) // 2
        if 0 <= gx < 5 and 0 <= gy < 7 and DIG[d][gy][gx] == "1":
            if fbm(x * 0.5, y * 0.5, 8) > 0.72:
                return (0, 0, 0, 0)
            return noisy(WHITE, 8)
    return (0, 0, 0, 0)


tile("number", 80, 128, 32, 16, True, number_px)
tile("warn", 80, 144, 16, 16, True, lambda x, y: noisy((196, 44, 32), 8) if (y // 4) % 2 == 0 else noisy((218, 214, 200), 6))
tile("red", 96, 144, 16, 16, False, lambda x, y: noisy(RED, 10))
tile("tire", 112, 128, 32, 32, False, lambda x, y: noisy((30, 30, 29), 3) if (y % 4) else noisy((20, 20, 19), 2))
tile("tireside", 144, 128, 32, 32, False, lambda x, y: noisy((36, 36, 34), 3))
tile("metal", 176, 128, 32, 32, False, lambda x, y: shade(noisy(DARKM, 5), 0.85 + fbm(x * .2, y * .2, 5) * .3))
tile("hull", 208, 128, 32, 32, False, lambda x, y: camo_color(x * 1.3, y * 1.3, 2))
tile("rust", 240, 128, 16, 32, False, lambda x, y: noisy(mix(RUST, RUST_L, fbm(x * .4, y * .4, 6)), 10))
tile("floor", 0, 160, 32, 32, False, lambda x, y: noisy((76, 76, 72), 4) if (x + 2 * y) % 6 == 0 else
     mix(noisy((54, 54, 52), 4), (70, 60, 44), 0.5 if fbm(x * .3, y * .3, 9) > 0.62 else 0))
tile("wall", 32, 160, 32, 32, False, lambda x, y: mix(noisy((100, 112, 98), 5), (72, 64, 50),
                                                     max(0, fbm(x * .2, y * .2, 10) - 0.55) * 3))
tile("canvas", 64, 160, 32, 32, False, lambda x, y: shade(noisy((114, 76, 48), 6), 0.8 if x % 8 == 0 else 1))
tile("leather", 96, 160, 32, 32, False, lambda x, y: shade(noisy((60, 47, 38), 5), 0.85 if y % 6 == 0 else 1))
_DIALS = [(5, 6, 3.5), (14, 6, 3.5), (23, 6, 3.5), (5, 16, 3), (13, 16, 3), (21, 16, 3), (28, 15, 2.2)]


def panel_px(x, y):
    for cx, cy, r in _DIALS:
        d = math.hypot(x + .5 - cx, y + .5 - cy)
        if d < r - 0.8:
            return (28, 30, 28) if abs((x - cx) - (y - cy) * 0.3) > 0.7 else (220, 220, 190)
        if d < r:
            return (150, 150, 140)
    if y in (23, 24) and x % 3 == 1:
        return (190, 50, 40)
    if y in (27, 28) and x % 4 == 2:
        return (200, 200, 190)
    return noisy((26, 28, 26), 3)


tile("panel", 128, 160, 32, 32, True, panel_px)
tile("crate", 160, 160, 32, 32, True, lambda x, y: shade(noisy((126, 94, 58), 7), 0.65 if y % 8 in (0, 7) or x in (0, 1, 30, 31) else 1))
tile("ammo", 192, 160, 32, 16, True, lambda x, y: (196, 172, 64) if y == 6 and 4 <= x <= 27 else shade(noisy((82, 88, 52), 5), 0.7 if x in (0, 31) or y in (0, 15) else 1))
tile("soot", 192, 176, 32, 16, False, lambda x, y: noisy((30, 28, 26), 5))
tile("grille", 224, 160, 32, 32, True, lambda x, y: (16, 16, 15) if x % 3 == 0 or y % 3 == 0 else noisy((48, 50, 46), 4))
tile("chrome", 0, 192, 32, 16, False, lambda x, y: noisy((156, 156, 150), 8))
tile("moss", 32, 192, 32, 32, False, lambda x, y: noisy((72, 86, 38), 10) if fbm(x * .3, y * .3, 12) > 0.45 else noisy((86, 68, 44), 8))
tile("cable", 64, 192, 32, 16, False, lambda x, y: noisy((38, 46, 36), 5) if (x + y) % 4 else (20, 20, 20))
tile("bladestrip", 96, 192, 128, 8, True, lambda x, y: shade(camo_color(x * 0.6, y * 2, 21), 0.8 if y in (0, 7) else (0.92 if x % 16 == 0 else 1)))
tile("bladeedge", 96, 200, 128, 8, False, lambda x, y: noisy((64, 68, 58), 4))


def intake_px(x, y):
    d = math.hypot(x - 15.5, y - 15.5)
    ang = math.atan2(y - 15.5, x - 15.5)
    if d < 4:
        return noisy((70, 72, 70), 5)
    if int((ang + math.pi) / (2 * math.pi) * 18) % 2 == 0:
        return noisy((22, 22, 21), 3)
    return noisy((42, 43, 41), 3)


tile("intake", 224, 192, 32, 32, True, intake_px)
tile("exhaust", 96, 208, 32, 16, False, lambda x, y: mix(noisy((64, 60, 54), 6), RUST, 0.35 if fbm(x * .3, y * .3, 31) > 0.6 else 0))
tile("interior_dark", 0, 208, 32, 16, False, lambda x, y: noisy((40, 44, 40), 4))
tile("glass_frame", 64, 208, 32, 16, False, lambda x, y: noisy((58, 64, 42), 5))

# ---------------------------------------------------------------------------
# Кубы
# ---------------------------------------------------------------------------
elements = []
FACE_AXES = {"north": (0, 1), "south": (0, 1), "east": (2, 1), "west": (2, 1), "up": (0, 2), "down": (0, 2)}
DENS = 2.0  # пикселей текстуры на единицу модели для «не целых» материалов


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


# ---------------------------------------------------------------------------
# Профиль фюзеляжа: z -> (a полуширина, yb низ, yt верх, n_top, n_bottom)
# Нос смотрит на север (-Z).
# ---------------------------------------------------------------------------
STATIONS = [
    (-48.4, 0.8, 9.3, 10.6, 2.0, 2.0),
    (-47.9, 2.8, 8.0, 12.8, 2.2, 2.2),
    (-47.0, 4.8, 6.9, 14.8, 2.4, 2.4),
    (-45.6, 6.7, 6.0, 17.2, 2.5, 2.8),
    (-43.8, 8.2, 5.5, 20.0, 2.6, 3.2),
    (-41.8, 9.2, 5.2, 22.5, 2.7, 3.6),
    (-39.5, 10.0, 5.0, 24.8, 2.8, 4.0),
    (-37.0, 10.5, 5.0, 26.6, 3.0, 4.2),
    (-34.0, 10.8, 5.0, 27.8, 3.2, 4.4),
    (-30.0, 11.0, 5.0, 28.4, 3.4, 4.5),
    (16.0, 11.0, 5.0, 28.5, 3.4, 4.5),
    (20.0, 10.9, 5.4, 28.5, 3.4, 4.3),
    (24.0, 10.4, 7.2, 28.3, 3.2, 3.8),
    (28.0, 9.3, 10.6, 28.0, 3.0, 3.2),
    (32.0, 7.9, 14.2, 27.7, 2.8, 2.9),
    (35.0, 6.8, 17.0, 27.4, 2.7, 2.7),
    (38.0, 6.0, 18.8, 27.2, 2.6, 2.6),
    (44.0, 5.2, 19.6, 26.9, 2.3, 2.3),
    (60.0, 4.3, 20.4, 26.3, 2.1, 2.1),
    (80.0, 3.4, 21.1, 25.7, 2.0, 2.0),
    (98.0, 2.7, 21.6, 25.2, 2.0, 2.0),
    (104.0, 2.1, 22.0, 25.0, 2.0, 2.0),
    (105.6, 0.7, 22.9, 24.3, 2.0, 2.0),
]


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


def make_profile(stations):
    zs = [s[0] for s in stations]
    fns = [pchip(zs, [s[j] for s in stations]) for j in range(1, 6)]
    return lambda z: tuple(f(z) for f in fns)


PROF = make_profile(STATIONS)


def spow(v, e):
    return math.copysign(abs(v) ** e, v)


def se_point(z, th, prof=PROF, xoff=0.0):
    a, yb, yt, nt, nb = prof(z)
    yc, h = (yt + yb) / 2, (yt - yb) / 2
    c = math.cos(th)
    n = nt if c >= 0 else nb
    return (xoff + a * spow(math.sin(th), 2 / n), yc + h * spow(c, 2 / n), z)


def halfwidth(z, y, prof=PROF):
    a, yb, yt, nt, nb = prof(z)
    yc, h = (yt + yb) / 2, (yt - yb) / 2
    c = max(-1, min(1, (y - yc) / h))
    n = nt if c >= 0 else nb
    cth = abs(c) ** (n / 2)
    return a * (max(0, 1 - cth * cth) ** 0.5) ** (2 / n)


def arc_thetas(n, z_ref, prof=PROF, th0=0.0, th1=2 * math.pi, closed=True):
    """Параметры θ с равной длиной дуги на эталонном сечении."""
    M = 4000
    ths = [th0 + (th1 - th0) * i / M for i in range(M + 1)]
    pts = [se_point(z_ref, t, prof) for t in ths]
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + length(sub(pts[i], pts[i - 1])))
    out, j = [], 0
    count = n if closed else n + 1
    for k in range(count):
        target = cum[-1] * k / n
        while j < M and cum[j + 1] < target:
            j += 1
        f = (target - cum[j]) / max(1e-9, cum[j + 1] - cum[j]) if j < M else 0
        out.append(ths[j] + (ths[min(j + 1, M)] - ths[j]) * f)
    return out


# ---------------------------------------------------------------------------
# Обшивка фюзеляжа + хвостовой балки
# ---------------------------------------------------------------------------
NSEG = 28
THETAS = arc_thetas(NSEG, 0.0)
Z_RINGS = [-48.4, -47.9, -47.0, -46.0, -44.8, -43.4, -41.8, -40.0, -38.0, -36.0, -33.5, -31.0,
           -28.5, -26.0, -24.0, -21.0, -18.0, -15.0, -12.0, -8.5, -5.0, -1.5, 2.0, 5.5, 9.0, 12.5,
           16.0, 20.0, 23.0, 26.0, 29.0, 32.0, 35.0, 38.0, 42.0, 47.0, 53.0, 59.0, 65.0, 71.0,
           77.0, 83.0, 89.0, 95.0, 100.0, 104.0, 105.6]
Z_SPLIT = 38.0          # граница развёрток A (кабина) и B (балка)
REG_A = (0, 0, 128, 128, -48.4, Z_SPLIT)
REG_B = (128, 0, 64, 128, Z_SPLIT, 105.6)
HULL_T = 0.6

fus_panels, side_door_panels, rear_L_panels, rear_R_panels = [], [], [], []
door_rects = {"side": [], "rear_L": [], "rear_R": []}


def is_glass(i, k, c):
    x, y, z = c
    if -38.0 <= z <= -36.0 or -28.5 <= z:
        return False  # стойки
    if -47.2 <= z <= -41.8 and 7.6 <= y <= 12.6 and abs(x) > 1.2:
        return True   # нижнее остекление носа
    if -47.6 <= z <= -28.5 and 15.0 <= y <= 26.6:
        if -36 < z and y > 25.0:
            return False
        if k % 4 == 0 or -44.8 <= z <= -43.4:
            return False  # рама остекления
        return True
    return False


def hull_uv(i, k):
    z0, z1 = Z_RINGS[i], Z_RINGS[i + 1]
    reg = REG_A if z1 <= Z_SPLIT + 1e-6 else REG_B
    u0, v0, w, h, za, zb = reg
    fu = lambda kk: u0 + w * kk / NSEG
    fv = lambda zz: v0 + h * (zz - za) / (zb - za)
    return [fu(k), fv(z0), fu(k + 1), fv(z1)]


def hull_dest(i, k, c):
    x, y, z = c
    if x < 0 and -24 < z < -15 and 8 < y < 24.5:
        door_rects["side"].append(hull_uv(i, k))
        return side_door_panels
    if 20 < z < Z_SPLIT and y < 18.5:
        key = "rear_L" if x < 0 else "rear_R"
        door_rects[key].append(hull_uv(i, k))
        return rear_L_panels if x < 0 else rear_R_panels
    return fus_panels


def hull_outer(i, k, c):
    return "glass" if is_glass(i, k, c) else hull_uv(i, k)


def hull_inner(i, k, c):
    if is_glass(i, k, c):
        return "glass"
    return "wall" if c[2] < 36 else "interior_dark"


rings = [[se_point(z, th) for th in THETAS] for z in Z_RINGS]
centers = [(0, (PROF(z)[1] + PROF(z)[2]) / 2, z) for z in Z_RINGS]
loft("hull", rings, centers, HULL_T, hull_outer, hull_dest, inner=hull_inner)
fus_panels += disc("nose_cap", (0, 9.95, -48.5), (0, 0, 1), 0.9, 0.3, "hull")
fus_panels += disc("boom_end_cap", (0, 23.6, 105.7), (0, 0, 1), 0.8, 0.3, "hull")


# --- роспись развёрток A и B по мировым координатам ---
def theta_at(kf):
    k0 = int(math.floor(kf)) % NSEG
    f = kf - math.floor(kf)
    t0 = THETAS[k0]
    t1 = THETAS[(k0 + 1) % NSEG] + (2 * math.pi if k0 + 1 == NSEG else 0)
    return lerp(t0, t1, f)


PANEL_Z = [-38, -28.5, -24, -15, -5, 5.5, 16, 26, 38, 53, 71, 89]
PANEL_Y = [9.5, 24.8]
STREAKS = [(RNG.uniform(-44, 100), RNG.uniform(14, 27), RNG.uniform(3, 9), RNG.choice((-1, 1))) for _ in range(26)]


def hull_px(x, y, z, seed):
    c = camo_color(z + (0 if x < 0 else 300), y * 1.4, seed)
    # грязь снизу и светлое брюхо
    if y < 9:
        c = mix(c, (84, 74, 52), min(0.55, (9 - y) * 0.12))
    if y < 6.2:
        c = mix(c, (98, 104, 86), 0.5)
    # копоть за выхлопными трубами
    if False:  # копоть от выхлопа больше не нужна
        s = math.exp(-(z + 2) / 26) * max(0, min(1, (y - 21) / 5))
        c = mix(c, (30, 28, 26), s * 0.75 * (0.7 + 0.3 * fbm(z * .5, y * .5, 30)))
    # потёки ржавчины
    for sz, sy, sl, sd in STREAKS:
        if (x < 0) == (sd < 0) and abs(z - sz) < 0.45 and sy - sl < y < sy:
            c = mix(c, RUST, 0.4 * (y - (sy - sl)) / sl + 0.1)
    # швы панелей и заклёпки
    tex_z = 0.34 if z < Z_SPLIT else 0.26
    for pz in PANEL_Z:
        if abs(z - pz) < tex_z:
            c = shade(c, 0.72)
    for py in PANEL_Y:
        if abs(y - py) < 0.28 and z < 36:
            c = shade(c, 0.78 if (int(z * 1.5) % 2) else 1.15)
    return c


def paint_region(reg, seed):
    u0, v0, w, h, za, zb = reg
    for py in range(h):
        z = za + (zb - za) * (py + 0.5) / h
        for px in range(w):
            kf = (px + 0.5) / w * NSEG
            x, y, _ = se_point(z, theta_at(kf))
            put(u0 + px, v0 + py, hull_px(x, y, z, seed))


paint_region(REG_A, 11)
paint_region(REG_B, 12)


def outline_rects(rects, col=(34, 36, 26)):
    if not rects:
        return
    us = [min(r[0], r[2]) for r in rects] + [max(r[0], r[2]) for r in rects]
    vs = [r[1] for r in rects] + [r[3] for r in rects]
    x0, x1, y0, y1 = int(round(min(us))), int(round(max(us))) - 1, int(round(min(vs))), int(round(max(vs))) - 1
    for x in range(x0, x1 + 1):
        for y in (y0, y1):
            put(x, y, col)
    for y in range(y0, y1 + 1):
        for x in (x0, x1):
            put(x, y, col)


for key in door_rects:
    outline_rects(door_rects[key])

# ---------------------------------------------------------------------------
# Декали (иллюминаторы, звёзды, номер) — тонкие кубы по касательной к обшивке
# ---------------------------------------------------------------------------


def surface_frame(side, z, y, prof=PROF):
    hw = halfwidth(z, y, prof)
    e = 0.05
    dy = (halfwidth(z, y + e, prof) - halfwidth(z, y - e, prof)) / (2 * e)
    dz = (halfwidth(z + e, y, prof) - halfwidth(z - e, y, prof)) / (2 * e)
    n = norm((side, -dy, -dz))
    return (side * hw, y, z), n


def decal(name, side, z, y, w, h, mat, offset=0.04, thick=0.2, inside=False, prof=PROF):
    P, n = surface_frame(side, z, y, prof)
    if inside:
        P = add(P, mul(n, -(HULL_T + offset)))
        n = mul(n, -1)
        side = -side
    else:
        P = add(P, mul(n, offset))
    Xh = (0, 0, 1) if side < 0 else (0, 0, -1)
    X = norm(sub(Xh, mul(n, dot(Xh, n))))
    Y = n
    Z = cross(X, Y)
    return ocube(name, P, X, Y, Z, (-w / 2, -thick, -h / 2), (w / 2, 0, h / 2),
                 {"up": mat, "down": mat, "north": "hull", "south": "hull", "east": "hull", "west": "hull"})


decals = []
PORTS_L = [-9.5, -2.5, 4.5, 11.5, 18.0]
PORTS_R = [-21.5, -14.5, -7.5, -0.5, 6.5, 13.5]
for zc in PORTS_L:
    decals.append(decal("porthole_L", -1, zc, 19.5, 4.2, 4.2, "porthole"))
    decals.append(decal("porthole_L_in", -1, zc, 19.5, 4.2, 4.2, "porthole", inside=True))
for zc in PORTS_R:
    decals.append(decal("porthole_R", 1, zc, 19.5, 4.2, 4.2, "porthole"))
    decals.append(decal("porthole_R_in", 1, zc, 19.5, 4.2, 4.2, "porthole", inside=True))
for side in (-1, 1):
    s = "L" if side < 0 else "R"
    decals.append(decal(f"star_boom_{s}", side, 52, 23.2, 5.5, 5.5, "star"))
    decals.append(decal(f"star_cabin_{s}", side, 27.5, 21.5, 6.5, 6.5, "star"))
decals.append(decal("number_L", -1, 7, 23.4, 7.2, 3.6, "number", offset=0.12))
decals.append(decal("number_R", 1, 18, 23.4, 7.2, 3.6, "number", offset=0.12))
decals.append(decal("number_boom_L", -1, 66, 23.3, 6, 3, "number"))
decals.append(decal("number_boom_R", 1, 66, 23.3, 6, 3, "number"))

# ---------------------------------------------------------------------------
# Пол, переборка, мелочи фюзеляжа
# ---------------------------------------------------------------------------
fus_misc = []


def floor_strips(z0, z1, y_top, dest, mat="floor"):
    zs = [z for z in Z_RINGS if z0 <= z <= z1]
    for a, b in zip(zs, zs[1:]):
        hw = min(halfwidth(a, y_top), halfwidth(b, y_top)) - HULL_T - 0.1
        if hw > 1:
            dest.append(cube("floor", [-hw, y_top - 0.8, a], [hw, y_top, b], "interior_dark", {"up": mat}))


floor_strips(-44.8, 20.0, 7.0, fus_misc)


def cap(name, z, t, dest, mat="wall", hole=None, rows=12, prof=PROF, faces=None):
    a, yb, yt, nt, nb = prof(z)
    ys = [yb + (yt - yb) * i / rows for i in range(rows + 1)]
    for y0, y1 in zip(ys, ys[1:]):
        hw = min(halfwidth(z, y0 + 0.01, prof), halfwidth(z, y1 - 0.01, prof)) - 0.2
        if hw < 0.3:
            continue
        spans = [(-hw, hw)]
        if hole and y1 > hole[2] and y0 < hole[3]:
            spans = [(-hw, hole[0]), (hole[1], hw)]
        for xa, xb in spans:
            if xb - xa > 0.2:
                dest.append(cube(name, [xa, y0, z - t / 2], [xb, y1, z + t / 2], mat, faces))


cap("bulkhead", -27.2, 0.8, fus_misc, "wall", hole=(-3, 3, 7, 23.2))

fus_misc += rod("door_rail", (-11.9, 25.2, -24.5), (-11.9, 25.2, -4.5), 0.4, "metal")
fus_misc.append(cube("door_step", [-13, 4.6, -23], [-10.6, 5.2, -16], "metal"))
fus_misc += rod("hoist_arm", (-10.8, 26.2, -22), (-15.2, 26.6, -22), 0.5, "metal")
fus_misc += rod("pitot_L", (-5.2, 12.8, -45.5), (-5.2, 12.8, -53), 0.25, "chrome")
fus_misc += rod("pitot_R", (5.2, 12.8, -45.5), (5.2, 12.8, -53), 0.25, "chrome")
fus_misc += rod("antenna_top", (0, 28, -6), (0, 32, -4.5), 0.2, "metal")
fus_misc += rod("antenna_belly", (0, 5.2, 10), (0, 2.5, 11.5), 0.2, "metal")
fus_misc += disc("beacon_red", (0, 28.6, 18.5), (0, 1, 0), 0.9, 0.8, "red")
fus_misc += rod("wiper_L", (-3, 15.8, -40.6), (-6, 20.5, -38.1), 0.15, "metal")
fus_misc += rod("wiper_R", (3, 15.8, -40.6), (6, 20.5, -38.1), 0.15, "metal")
fus_misc += rod("mirror_arm", (-9.6, 16, -41), (-12.5, 16.6, -42), 0.2, "metal")
fus_misc.append(cube("mirror", [-13.3, 15.8, -42.6], [-12.3, 17.4, -42.3], "metal", origin=[-12.8, 16.6, -42.4], rot=[0, 20, 0]))
_winch = []
tube("hoist_winch", [(-15.4, 26.8, -24), (-15.4, 26.8, -20)], [1.2, 1.2], 8, _winch, "metal", "metal")
fus_misc += _winch

# ---------------------------------------------------------------------------
# Кабина пилотов (интерьер)
# ---------------------------------------------------------------------------
ck = []
ck.append(cube("instrument_panel", [-7.8, 13, -41.0], [7.8, 18.4, -40.2], "metal", {"south": "panel"},
               origin=[0, 13, -40.6], rot=[-18, 0, 0]))
ck.append(cube("panel_hood", [-8, 18.2, -41.8], [8, 19.0, -39.0], "leather", origin=[0, 18.6, -40.4], rot=[-8, 0, 0]))
ck.append(cube("center_console", [-1.6, 7, -40], [1.6, 12, -31], "metal", {"up": "panel"}))
ck.append(cube("overhead_panel", [-3, 25.2, -36], [3, 26.2, -29], "metal", {"down": "panel"}))
for side, x in (("L", -4.6), ("R", 4.6)):
    ck.append(cube(f"seat_base_{side}", [x - 2.1, 7, -34.5], [x + 2.1, 10, -30.5], "metal"))
    ck.append(cube(f"seat_cushion_{side}", [x - 2.4, 10, -35], [x + 2.4, 11.2, -30], "leather"))
    ck.append(cube(f"seat_back_{side}", [x - 2.4, 11, -30.4], [x + 2.4, 19.5, -29.2], "leather",
                   origin=[x, 11, -29.8], rot=[12, 0, 0]))
    ck.append(cube(f"headrest_{side}", [x - 1.5, 19.3, -29.6], [x + 1.5, 21.4, -28.6], "leather",
                   origin=[x, 11, -29.8], rot=[12, 0, 0]))
    ck += rod(f"cyclic_{side}", (x, 7, -35.5), (x, 13, -37), 0.28, "metal")
    ck.append(cube(f"cyclic_grip_{side}", [x - 0.5, 12.8, -37.6], [x + 0.5, 14.3, -36.6], "leather"))
    ck += rod(f"collective_{side}", (x - 3.0 if x < 0 else x + 3.0, 8, -30), (x - 3.0 if x < 0 else x + 3.0, 10, -34), 0.25, "metal")
    ck.append(cube(f"pedals_{side}", [x - 1.9, 7, -39.6], [x + 1.9, 8.2, -39.0], "metal", origin=[x, 7, -39.3], rot=[-30, 0, 0]))
ck.append(cube("engineer_seat", [-2, 13, -28.6], [2, 13.8, -26.4], "canvas"))
ck.append(cube("radio_rack", [5, 7, -28.9], [9, 16, -27.6], "metal", {"south": "panel"}))

# ---------------------------------------------------------------------------
# Интерьер грузовой кабины
# ---------------------------------------------------------------------------
cab = []
cab.append(cube("bench_L_seat", [-9.8, 11.6, -12], [-6, 12.4, 20], "canvas"))
cab.append(cube("bench_L_back", [-10.2, 13, -12], [-9.6, 21, 20], "canvas"))
cab.append(cube("bench_R_seat", [6, 11.6, -24], [9.8, 12.4, 20], "canvas"))
cab.append(cube("bench_R_back", [9.6, 13, -24], [10.2, 21, 20], "canvas"))
for z in range(-10, 21, 6):
    cab += rod("bench_L_leg", (-6.6, 7, z), (-6.6, 11.6, z), 0.25, "chrome")
for z in range(-22, 21, 6):
    cab += rod("bench_R_leg", (6.6, 7, z), (6.6, 11.6, z), 0.25, "chrome")
cab += rod("roof_rail_L", (-6, 26.4, -25), (-6, 26.4, 20), 0.25, "chrome")
cab += rod("roof_rail_R", (6, 26.4, -25), (6, 26.4, 20), 0.25, "chrome")
cab += rod("floor_rail_L", (-4, 7.1, -26), (-4, 7.1, 20), 0.25, "metal")
cab += rod("floor_rail_R", (4, 7.1, -26), (4, 7.1, 20), 0.25, "metal")
for z in (-18, -2, 14):
    cab += disc("cabin_lamp", (0, 27.3, z), (0, 1, 0), 1.1, 0.6, "chrome")
cab += rod("cable_run", (-8.8, 24.4, -26), (-8.8, 24.4, 20), 0.4, "cable")
cab += rod("heater_duct", (8.6, 23.4, -26), (8.6, 23.4, 20), 0.9, "metal")
_aux = []
tube("aux_fuel_tank", [(3.5, 10.5, -25.5), (3.5, 10.5, -24.8), (3.5, 10.5, -16.2), (3.5, 10.5, -15.5)],
     [(1.8, 2.2), (2.6, 3.2), (2.6, 3.2), (1.8, 2.2)], 12, _aux, "hull", "hull")
cab += _aux
cab.append(cube("crate_big", [-6, 7, 12], [0, 13, 19.5], "crate"))
cab.append(cube("crate_small", [-5, 13, 14], [-1, 17, 18], "crate", origin=[-3, 13, 16], rot=[0, 15, 0]))
cab.append(cube("ammo_box_1", [1.5, 7, 14], [5.5, 10, 19.5], "ammo"))
cab.append(cube("ammo_box_2", [2, 10, 15], [5, 12.5, 19], "ammo", origin=[3.5, 10, 17], rot=[0, -20, 0]))
cab.append(cube("ammo_box_open", [-8, 7, -6], [-4, 9.5, -2], "ammo", {"up": "soot"}))
_ext = []
tube("fire_extinguisher", [(7.8, 7.1, -25.2), (7.8, 12.5, -25.2), (7.8, 13.2, -25.2)], [0.8, 0.8, 0.4], 8, _ext, "red", "red",
     ref=(1, 0, 0))
cab += _ext
cab.append(cube("first_aid", [9.3, 20, -12], [10.2, 23, -8], "red"))
cab.append(cube("stretcher", [-2, 7.3, -8], [3, 7.9, 8], "canvas", origin=[0, 7, 0], rot=[0, 10, 0]))
cab.append(cube("helmet", [-8.6, 12.4, 2], [-7, 13.6, 3.6], "hull"))
cab.append(cube("moss_patch", [-8, 7.02, 15], [-3, 7.2, 20], "moss"))
cab.append(cube("debris_panel", [3, 7, -4], [7, 7.4, 1], "rust", origin=[5, 7, -1.5], rot=[0, 30, 8]))

# ---------------------------------------------------------------------------
# Пилон несущего винта: невысокий гладкий обтекатель прямо на крыше
# (капот двигателей, воздухозаборники и выхлоп убраны)
# ---------------------------------------------------------------------------
HUB_Y = 33.4
eng = []
_py = []
tube("rotor_pylon", [(0, 27.6, -13), (0, 29.2, -13), (0, 30.6, -13), (0, 31.4, -13), (0, 31.8, -13)],
     [(5.2, 7.4), (4.6, 6.4), (3.2, 4.4), (1.9, 2.4), (1.2, 1.4)], 18, _py, "hull", "interior_dark", ref=(1, 0, 0))
eng += _py
_mast = []
tube("rotor_mast", [(0, 31.2, -13), (0, HUB_Y - 0.4, -13)], [1.2, 1.05], 10, _mast, "metal", "metal", ref=(1, 0, 0))
eng += _mast
eng += disc("swashplate", (0, 32.0, -13), (0, 1, 0), 2.6, 0.6, "metal")

# ---------------------------------------------------------------------------
# Топливные баки (капсулы) и хвостовое оперение
# ---------------------------------------------------------------------------
tanks = []


def fuel_tank(name, x, z0, z1, rx, ry, yc):
    n = 10
    zs, rs = [], []
    for i in range(n + 1):
        f = i / n
        z = lerp(z0, z1, f)
        e = abs(2 * f - 1)
        k = (max(0.0, 1 - e ** 5)) ** 0.5
        zs.append((x, yc, z))
        rs.append((max(0.25, rx * k), max(0.25, ry * k)))
    tube(name, zs, rs, 16, tanks, "hull", "interior_dark", t=0.4, ref=(1, 0, 0))


fuel_tank("fuel_tank_L", -13.4, -16, 10, 2.4, 3.1, 11.0)
fuel_tank("fuel_tank_R", 13.4, -23, 10, 2.4, 3.1, 11.0)
for z in (-8, 2):
    tanks += rod("tank_strap_L", (-11, 14.4, z), (-15.9, 11, z), 0.25, "metal")
    tanks += rod("tank_strap_R", (11, 14.4, z), (15.9, 11, z), 0.25, "metal")
tanks += rod("tank_strap_R2", (11, 14.4, -15), (15.9, 11, -15), 0.25, "metal")

tail = []
# киль (профиль крыла, наклон 30° назад)
FIN_ROOT, FIN_DIR = (0, 21.6, 97.0), (0, math.cos(math.radians(30)), math.sin(math.radians(30)))
fin_path = [add(FIN_ROOT, mul(FIN_DIR, s)) for s in (0, 5, 10, 15, 18.5, 19.6)]
tube("tail_fin", fin_path, [(1.3, 7.0), (1.15, 6.2), (1.0, 5.3), (0.9, 4.5), (0.8, 3.8), (0.35, 2.2)], 12, tail,
     "hull", "interior_dark", t=0.35, ref=(1, 0, 0))
# стабилизаторы
for sgn in (-1, 1):
    s = "L" if sgn < 0 else "R"
    stab = [(sgn * x, 22.8, 91.5) for x in (2.0, 5, 9, 12.2, 12.7)]
    tube(f"stabilizer_{s}", stab, [(0.55, 3.6), (0.5, 3.4), (0.45, 3.0), (0.4, 2.7), (0.15, 1.6)], 10, tail,
         "hull", "interior_dark", t=0.25, ref=(0, 1, 0))
    tail += disc(f"stab_tip_{s}", (sgn * 12.4, 22.8, 91.5), (1, 0, 0), 1.2, 0.4, "warn")
tail += rod("tail_skid_strut", (0, 21.3, 90), (0, 16.5, 92.5), 0.35, "metal")
tail += rod("tail_skid_pad", (0, 16.2, 91.2), (0, 16.2, 95.2), 0.5, "metal")
tail += rod("driveshaft_cover", (0, 26.9, 38), (0, 25.4, 96), 0.9, "metal")
TR = (2.6, 37.3, 107.8)
_tg = []
tube("tail_gearbox", [(-0.8, TR[1], TR[2]), (0.8, TR[1], TR[2]), (2.0, TR[1], TR[2])], [(1.9, 2.2), (1.9, 2.2), (1.2, 1.2)],
     12, _tg, "metal", "metal", ref=(0, 1, 0))
tail += _tg
tail += disc("tail_light", (0, 39.8, 109.5), (0, 0, 1), 0.5, 0.6, "chrome")

# ---------------------------------------------------------------------------
# Несущий винт (5 лопастей) и рулевой винт (3 лопасти)
# ---------------------------------------------------------------------------
HUB = (0, HUB_Y, -13)
rotor_children = []
rotor_children += disc("hub_plate_low", (0, HUB_Y - 0.5, -13), (0, 1, 0), 3.2, 1.0, "metal")
rotor_children += disc("hub_plate_high", (0, HUB_Y + 0.7, -13), (0, 1, 0), 2.6, 1.2, "metal")
rotor_children += disc("hub_cap", (0, HUB_Y + 1.7, -13), (0, 1, 0), 1.4, 0.9, "metal")
for k in range(5):
    blade = []
    blade += rod(f"blade{k}_hinge", (2.4, HUB_Y, -13), (8.5, HUB_Y, -13), 0.8, "metal")
    blade += rod(f"blade{k}_damper", (2.4, HUB_Y + 1.0, -12.2), (7, HUB_Y + 0.8, -12.2), 0.35, "chrome")
    blade.append(cube(f"blade{k}", [8.5, HUB_Y - 0.3, -15.1], [84, HUB_Y + 0.25, -11.1], "bladeedge",
                      {"up": "bladestrip", "down": "bladestrip"}))
    blade.append(cube(f"blade{k}_te", [8.5, HUB_Y - 0.2, -11.1], [84, HUB_Y + 0.1, -10.5], "bladeedge"))
    blade.append(cube(f"blade{k}_tip", [84, HUB_Y - 0.3, -15.1], [88, HUB_Y + 0.25, -11.1], "warn"))
    rotor_children.append(group(f"blade_{k}", HUB, blade, rotation=[0, k * 72, 0]))
main_rotor = group("main_rotor", HUB, rotor_children)

tr_children = disc("tail_rotor_hub", (3.0, TR[1], TR[2]), (1, 0, 0), 1.3, 1.4, "metal")
tr_children += disc("tail_rotor_cap", (3.9, TR[1], TR[2]), (1, 0, 0), 0.7, 0.8, "metal")
for k in range(3):
    tr_children.append(group(f"tr_blade_{k}", TR, [
        cube(f"tr_blade{k}", [2.8, TR[1] + 1.2, TR[2] - 1.15], [3.3, TR[1] + 13.5, TR[2] + 1.15], "bladeedge",
             {"east": "bladestrip", "west": "bladestrip"}),
        cube(f"tr_blade{k}_tip", [2.8, TR[1] + 13.5, TR[2] - 1.15], [3.3, TR[1] + 16, TR[2] + 1.15], "warn"),
    ], rotation=[k * 120, 0, 0]))
tail_rotor = group("tail_rotor", TR, tr_children)
tail.append(tail_rotor)

# ---------------------------------------------------------------------------
# Шасси: круглые колёса (тор из панелей + боковины-диски)
# ---------------------------------------------------------------------------


def wheel(name, c, r, w):
    out = []
    x = c[0]
    prof = [(-w / 2, r * 0.8), (-w * 0.36, r * 0.96), (-w * 0.12, r), (w * 0.12, r), (w * 0.36, r * 0.96), (w / 2, r * 0.8)]
    tube(name, [(x + dx, c[1], c[2]) for dx, _ in prof], [rr for _, rr in prof], 20, out, "tire", "tireside",
         t=0.5, ref=(0, 1, 0), edge="tire")
    for sgn in (-1, 1):
        out += disc(f"{name}_side", (x + sgn * (w / 2 - 0.1), c[1], c[2]), (1, 0, 0), r * 0.82, 0.3, "tireside")
        out += disc(f"{name}_rim", (x + sgn * (w / 2 + 0.05), c[1], c[2]), (1, 0, 0), r * 0.5, 0.35, "chrome")
        out += disc(f"{name}_hub", (x + sgn * (w / 2 + 0.3), c[1], c[2]), (1, 0, 0), r * 0.22, 0.4, "metal")
    return out


def main_gear(sgn):
    s = "L" if sgn < 0 else "R"
    parts = wheel(f"wheel_main_{s}", (sgn * 17.6, 4.3, 1.5), 4.3, 3.2)
    parts += rod(f"axle_{s}", (sgn * 15.6, 4.3, 1.5), (sgn * 16.2, 4.3, 1.5), 0.6, "metal")
    parts += rod(f"oleo_low_{s}", (sgn * 15.9, 4.3, 1.5), (sgn * 14.3, 11, 1.5), 0.55, "chrome")
    parts += rod(f"oleo_up_{s}", (sgn * 14.6, 9.8, 1.5), (sgn * 11.4, 17.2, 1.5), 0.85, "metal")
    parts += rod(f"brace_front_{s}", (sgn * 15.8, 4.3, 1.5), (sgn * 6.0, 5.4, -4.0), 0.4, "metal")
    parts += rod(f"brace_rear_{s}", (sgn * 15.8, 4.3, 1.5), (sgn * 6.0, 5.4, 7.0), 0.4, "metal")
    return group(f"gear_main_{s}", (sgn * 11.4, 17.2, 1.5), parts)


nose = []
nose += rod("nose_strut", (0, 3.4, -40.2), (0, 6.2, -41.6), 0.45, "chrome")
nose += rod("nose_axle", (-2.9, 3.3, -40.2), (2.9, 3.3, -40.2), 0.35, "metal")
nose += wheel("wheel_nose_L", (-1.95, 3.3, -40.2), 3.2, 1.8)
nose += wheel("wheel_nose_R", (1.95, 3.3, -40.2), 3.2, 1.8)
gear_nose = group("gear_nose", (0, 6.2, -41.6), nose)

# ---------------------------------------------------------------------------
# Двери
# ---------------------------------------------------------------------------
side_door = group("side_door", (-11.5, 7, -24), side_door_panels + [
    cube("side_door_handle", [-11.9, 15, -17], [-11.4, 15.8, -15.8], "chrome"),
    cube("side_door_handle_in", [-10.4, 15, -17], [-9.9, 15.8, -15.8], "chrome"),
    decal("side_door_window", -1, -19.5, 19.5, 3.6, 3.6, "porthole", offset=0.06),
])
cockpit_door = group("cockpit_door", (3, 7, -27.2), [
    cube("cockpit_door_panel", [-3, 7, -27.5], [3, 23.2, -26.9], "wall"),
    cube("cockpit_door_window", [-1.5, 17, -27.6], [1.5, 20, -26.8], "porthole"),
    cube("cockpit_door_handle", [-2.6, 14, -26.8], [-1.8, 14.6, -26.4], "chrome"),
])
rear_L = group("rear_door_L", (-halfwidth(20, 12), 7, 20), rear_L_panels + [
    cube("rear_door_handle_L", [-4, 13, 29.3], [-2, 13.5, 29.8], "chrome", origin=[-3, 13, 29.5], rot=[0, -20, 0])])
rear_R = group("rear_door_R", (halfwidth(20, 12), 7, 20), rear_R_panels)

# ---------------------------------------------------------------------------
# Иерархия
# ---------------------------------------------------------------------------
body = group("body", (0, 18, 0), [
    group("fuselage", (0, 18, 0), fus_panels + fus_misc + decals),
    group("cockpit", (0, 12, -34), ck),
    group("cabin_interior", (0, 12, 0), cab),
    group("rotor_pylon", (0, 30, -13), eng),
    group("fuel_tanks", (0, 11, -5), tanks),
    group("tail", (0, 24, 60), tail),
    side_door, cockpit_door, rear_L, rear_R,
])
gear = group("landing_gear", (0, 6, 0), [main_gear(-1), main_gear(1), gear_nose])
root = group("helicopter", (0, 18, 0), [body, main_rotor, gear])
root["isOpen"] = True
body["isOpen"] = True

GROUPS = {}


def index(g):
    GROUPS[g["name"]] = g
    for c in g["children"]:
        if isinstance(c, dict):
            index(c)


index(root)

# ---------------------------------------------------------------------------
# Анимации. Blockbench (как Bedrock) инвертирует X/Y вращения и X позиции
# у костей в анимациях — значения ниже заданы с учётом этого.
# ---------------------------------------------------------------------------


def kf(channel, t, xyz, interp="linear"):
    return {"channel": channel, "data_points": [{"x": str(round(xyz[0], 3)), "y": str(round(xyz[1], 3)),
                                                  "z": str(round(xyz[2], 3))}],
            "uuid": new_uuid(), "time": round(t, 4), "color": -1, "interpolation": interp}


def animation(name, length, loop, tracks):
    animators = {}
    for bone, chans in tracks.items():
        g = GROUPS[bone]
        keys = []
        for ch, pts in chans.items():
            for p in pts:
                keys.append(kf(ch, p[0], p[1], p[2] if len(p) > 2 else "linear"))
        animators[g["uuid"]] = {"name": bone, "type": "bone", "keyframes": keys}
    return {"uuid": new_uuid(), "name": name, "loop": loop, "override": False, "length": length,
            "snapping": 20, "selected": False, "anim_time_update": "", "blend_weight": "",
            "start_delay": "", "loop_delay": "", "animators": animators}


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


Z3 = (0, 0, 0)
FLY_H = 32
GEAR_DOWN = (0, -0.6, 0)
anims = [
    animation("rotor_idle", 1.0, "loop", {
        "main_rotor": {"rotation": spin(1, 1.0, 1)},
        "tail_rotor": {"rotation": spin(0, 1.0, 5)},
        "body": {"position": [(i * 0.05, (0.03 * ((i // 2) % 2 * 2 - 1) if i % 4 == 3 else 0, 0.05 if i % 2 else 0, 0))
                              for i in range(21)]},
    }),
    animation("rotor_startup", 6.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": ramp_spin(1, 0, 6, 360)},
        "tail_rotor": {"rotation": ramp_spin(0, 0, 6, 1800)},
    }),
    animation("rotor_shutdown", 6.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": ramp_spin(1, 0, 6, 360, speed_up=False)},
        "tail_rotor": {"rotation": ramp_spin(0, 0, 6, 1800, speed_up=False)},
    }),
    animation("hover", 2.0, "loop", {
        "main_rotor": {"rotation": spin(1, 2.0, 4)},
        "tail_rotor": {"rotation": spin(0, 2.0, 16)},
        "helicopter": {"position": wave([(1, 1.2, 1), (0, 0.4, 1)], 2.0, 8, base=(0, FLY_H, 0)),
                       "rotation": wave([(0, 1.2, 1), (2, 1.5, 1)], 2.0, 8, phase=1.2)},
        "landing_gear": {"position": [(0, GEAR_DOWN)]},
    }),
    animation("fly_forward", 2.0, "loop", {
        "main_rotor": {"rotation": spin(1, 2.0, 4)},
        "tail_rotor": {"rotation": spin(0, 2.0, 16)},
        "helicopter": {"position": wave([(1, 0.8, 1)], 2.0, 8, base=(0, FLY_H, 0)),
                       "rotation": wave([(0, 1.0, 1), (2, 1.2, 1)], 2.0, 8, phase=0.7, base=(12, 0, 0))},
        "landing_gear": {"position": [(0, GEAR_DOWN)]},
    }),
    animation("takeoff", 5.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": [(0, Z3), (1, (0, 540, 0)), (2, (0, 1260, 0)), (3, (0, 1980, 0)),
                                    (4, (0, 2700, 0)), (5, (0, 3420, 0))]},
        "tail_rotor": {"rotation": [(0, Z3), (5, (5 * 2880, 0, 0))]},
        "helicopter": {"position": [(0, Z3), (1.5, Z3, "catmullrom"), (2.2, (0, 2, 0), "catmullrom"),
                                    (3.5, (0, 16, 0), "catmullrom"), (5, (0, FLY_H, 0), "catmullrom")],
                       "rotation": [(0, Z3), (1.5, Z3, "catmullrom"), (2.2, (-3, 0, 0), "catmullrom"),
                                    (3.5, (4, 0, 0), "catmullrom"), (5, Z3, "catmullrom")]},
        "landing_gear": {"position": [(0, Z3), (1.5, Z3), (2.2, GEAR_DOWN)]},
    }),
    animation("landing", 5.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": [(0, Z3), (1, (0, 720, 0)), (2, (0, 1440, 0)), (3, (0, 2100, 0)),
                                    (4, (0, 2640, 0)), (5, (0, 3060, 0))]},
        "tail_rotor": {"rotation": [(0, Z3), (5, (5 * 2400, 0, 0))]},
        "helicopter": {"position": [(0, (0, FLY_H, 0)), (1.8, (0, 12, 0), "catmullrom"),
                                    (3.2, (0, 1.5, 0), "catmullrom"), (3.8, (0, -0.4, 0), "catmullrom"),
                                    (4.2, Z3, "catmullrom"), (5, Z3)],
                       "rotation": [(0, Z3), (1.8, (-5, 0, 0), "catmullrom"), (3.2, (-2, 0, 0), "catmullrom"),
                                    (3.8, (0.8, 0, 0), "catmullrom"), (4.2, Z3, "catmullrom"), (5, Z3)]},
        "landing_gear": {"position": [(0, GEAR_DOWN), (3.6, GEAR_DOWN), (3.8, (0, 0.4, 0)), (4.2, Z3)]},
    }),
    animation("side_door_open", 1.2, "hold_on_last_frame", {
        "side_door": {"position": [(0, Z3), (0.3, (1.4, 0, 0), "catmullrom"), (1.2, (1.4, 0, 9.4), "catmullrom")]},
    }),
    animation("side_door_close", 1.2, "hold_on_last_frame", {
        "side_door": {"position": [(0, (1.4, 0, 9.4)), (0.9, (1.4, 0, 0), "catmullrom"), (1.2, Z3, "catmullrom")]},
    }),
    animation("rear_doors_open", 1.6, "hold_on_last_frame", {
        "rear_door_L": {"rotation": [(0, Z3), (1.6, (0, 105, 0), "catmullrom")]},
        "rear_door_R": {"rotation": [(0, Z3), (0.2, Z3), (1.6, (0, -105, 0), "catmullrom")]},
    }),
    animation("rear_doors_close", 1.6, "hold_on_last_frame", {
        "rear_door_L": {"rotation": [(0, (0, 105, 0)), (0.2, (0, 105, 0)), (1.6, Z3, "catmullrom")]},
        "rear_door_R": {"rotation": [(0, (0, -105, 0)), (1.4, Z3, "catmullrom")]},
    }),
    animation("cockpit_door_open", 0.8, "hold_on_last_frame", {
        "cockpit_door": {"rotation": [(0, Z3), (0.8, (0, -95, 0), "catmullrom")]},
    }),
    animation("cockpit_door_close", 0.8, "hold_on_last_frame", {
        "cockpit_door": {"rotation": [(0, (0, -95, 0)), (0.8, Z3, "catmullrom")]},
    }),
    animation("abandoned_wind", 4.0, "loop", {
        "main_rotor": {"rotation": wave([(1, 4, 1)], 4.0, 8)},
        **{f"blade_{k}": {"rotation": wave([(2, 1.5, 1)], 4.0, 8, phase=k * 1.1)} for k in range(5)},
        "tail_rotor": {"rotation": wave([(0, 12, 1)], 4.0, 8, phase=0.5)},
        "side_door": {"position": wave([(2, 0.4, 2)], 4.0, 8, base=(1.4, 0, 3))},
        "rear_door_L": {"rotation": wave([(1, 3, 1)], 4.0, 8, phase=2, base=(0, 25, 0))},
    }),
    animation("crash", 4.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": [(0, Z3), (1, (0, 700, 0)), (2, (0, 1300, 0)), (3, (0, 1750, 0)),
                                    (3.3, (0, 1850, 0)), (4, (0, 1880, 0), "catmullrom")]},
        "tail_rotor": {"rotation": [(0, Z3), (0.4, (500, 0, 0)), (0.6, (560, 0, 0))]},
        "helicopter": {"position": [(0, (0, FLY_H, 0)), (1, (2, 28, 3), "catmullrom"), (2, (6, 18, 6), "catmullrom"),
                                    (3, (8, 4, 8), "catmullrom"), (3.3, (8.5, 0, 8.5), "catmullrom"),
                                    (3.5, (8.6, 1.2, 8.6), "catmullrom"), (4, (8.8, 0, 8.8), "catmullrom")],
                       "rotation": [(0, Z3), (1, (6, 150, -4), "catmullrom"), (2, (10, 400, -8), "catmullrom"),
                                    (3, (12, 600, -12), "catmullrom"), (3.3, (8, 640, -18), "catmullrom"),
                                    (3.6, (4, 648, -16), "catmullrom"), (4, (5, 650, -17), "catmullrom")]},
        "landing_gear": {"position": [(0, GEAR_DOWN), (3.2, GEAR_DOWN), (3.4, (0, 1.4, 0))]},
        **{f"blade_{k}": {"rotation": [(0, Z3), (3.3, Z3), (3.5, (0, 0, -6 - 2 * k), "catmullrom"),
                                       (4, (0, 0, -8 - 2 * k), "catmullrom")]} for k in range(5)},
    }),
]

# ---------------------------------------------------------------------------


def png_bytes():
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in img)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", TEX, TEX, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


tex_png = png_bytes()
with open(os.path.join(HERE, "mi8_texture.png"), "wb") as f:
    f.write(tex_png)

model = {
    "meta": {"format_version": "4.10", "model_format": "free", "box_uv": False},
    "name": "mi8_helicopter",
    "model_identifier": "mi8_helicopter",
    "visible_box": [10, 6, 1],
    "variable_placeholders": "",
    "variable_placeholder_buttons": [],
    "timeline_setups": [],
    "unhandled_root_fields": {},
    "resolution": {"width": TEX, "height": TEX},
    "elements": elements,
    "outliner": [root],
    "textures": [{
        "path": "", "name": "mi8_texture.png", "folder": "", "namespace": "", "id": "0",
        "group": "", "width": TEX, "height": TEX, "uv_width": TEX, "uv_height": TEX,
        "particle": False, "use_as_default": True, "layers_enabled": False, "sync_to_project": "",
        "render_mode": "default", "render_sides": "auto", "pbr_channel": "color",
        "frame_time": 1, "frame_order_type": "loop", "frame_order": "", "frame_interpolate": False,
        "visible": True, "internal": True, "saved": False, "uuid": new_uuid(), "relative_path": "",
        "source": "data:image/png;base64," + base64.b64encode(tex_png).decode(),
    }],
    "animations": anims,
}
with open(os.path.join(HERE, "mi8_helicopter.bbmodel"), "w", encoding="utf-8") as f:
    json.dump(model, f, ensure_ascii=False, separators=(",", ":"))
print(f"elements: {len(elements)}, groups: {len(GROUPS)}, animations: {len(anims)}")


# ---------------------------------------------------------------------------
# Экспорт для Paper-плагина: ресурспак Java 26.1.2 (модели предметов по частям)
# Каждая подвижная часть — отдельная модель предмета, которую плагин показывает
# через ItemDisplay. Геометрия ужата в 4 раза, чтобы уложиться в лимит
# Java-моделей (-16..32), плагин растягивает её обратно (масштаб 8 = 1 блок на 8 ед.).
# ---------------------------------------------------------------------------
# Порядок осей свободного поворота элементов в Java 26.1+. По умолчанию — как в
# Blockbench (ZYX: сначала X, потом Y, потом Z). Если в игре панели корпуса
# встали криво — поменяйте на "XYZ" и перезапустите генератор.
JAVA_ROTATION_ORDER = "ZYX"
BLOCKS_PER_UNIT = 1 / 8     # 8 единиц модели = 1 блок (Ми-8 ≈ 19 блоков в длину)
JAVA_SHRINK = 4
PARTS = {  # часть: (группа или None для «всего остального», точка поворота)
    "mi8_body": (None, (0, 20, 28)),
    "mi8_main_rotor": ("main_rotor", None),
    "mi8_tail_rotor": ("tail_rotor", None),
    "mi8_side_door": ("side_door", None),
    "mi8_cockpit_door": ("cockpit_door", None),
    "mi8_rear_door_l": ("rear_door_L", None),
    "mi8_rear_door_r": ("rear_door_R", None),
}
ELS = {e["uuid"]: e for e in elements}


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


I3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


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
            # Java 26.1+: свободный поворот по трём осям (тот же порядок, что в Blockbench)
            je["rotation"] = {"origin": o, "x": ang[0], "y": ang[1], "z": ang[2]}
    for f, fd in e["faces"].items():
        je["faces"][f] = {"uv": [round(u * 16 / TEX, 4) for u in fd["uv"]], "texture": "#0"}
    return je


def export_java():
    rp = os.path.join(PLUGIN, "resourcepack")
    moved = {g for g, _ in PARTS.values() if g}
    parts_yml = ["# Сгенерировано blockbench/mi8_helicopter/generate.py — не править вручную",
                 f"blocks-per-unit: {BLOCKS_PER_UNIT}", f"display-scale: {JAVA_SHRINK * 16 * BLOCKS_PER_UNIT}", "parts:"]
    files = {}
    for part, (gname, pivot) in PARTS.items():
        items = []
        if gname:
            g = GROUPS[gname]
            pivot = tuple(g["origin"])
            collect(g, I3, (0, 0, 0), items, set())
        else:
            collect(root, I3, (0, 0, 0), items, moved)
        model = {"textures": {"0": "heli:item/mi8", "particle": "heli:item/mi8"},
                 "elements": [java_element(e, Ra, ta, pivot) for e, Ra, ta in items]}
        files[f"assets/heli/models/item/{part}.json"] = json.dumps(model, separators=(",", ":"))
        files[f"assets/heli/items/{part}.json"] = json.dumps(
            {"model": {"type": "minecraft:model", "model": f"heli:item/{part}"}})
        pv = [round(c * BLOCKS_PER_UNIT, 5) for c in pivot]
        parts_yml.append(f"  {part}: {{pivot: [{pv[0]}, {pv[1]}, {pv[2]}], elements: {len(items)}}}")
    files["assets/heli/textures/item/mi8.png"] = tex_png
    files["pack.mcmeta"] = json.dumps({"pack": {
        "description": "Mi-8 helicopter (heli plugin)", "min_format": 69, "max_format": 999}}, indent=2)
    zpath = os.path.join(PLUGIN, "src", "main", "resources", "mi8_resourcepack.zip")
    os.makedirs(os.path.dirname(zpath), exist_ok=True)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, data)
    with open(os.path.join(PLUGIN, "src", "main", "resources", "mi8_parts.yml"), "w", encoding="utf-8") as f:
        f.write("\n".join(parts_yml) + "\n")
    print("resource pack:", os.path.relpath(zpath, HERE), f"{os.path.getsize(zpath) // 1024} KB")


export_java()
