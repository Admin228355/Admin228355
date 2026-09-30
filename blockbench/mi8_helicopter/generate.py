#!/usr/bin/env python3
"""Генератор Blockbench-модели вертолёта «Ми-8» (зона отчуждения).

Создаёт:
  mi8_helicopter.bbmodel  — проект Blockbench (Generic Model) с встроенной
                            текстурой 64x64, группами (костями) и анимациями;
  mi8_texture.png         — та же текстура 64x64 отдельным файлом.

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
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
RNG = random.Random(1986)
TEX = 64


def new_uuid():
    return str(uuid.UUID(int=RNG.getrandbits(128), version=4))


# ---------------------------------------------------------------------------
# Текстура 64x64
# ---------------------------------------------------------------------------
img = [[(0, 0, 0, 255) for _ in range(TEX)] for _ in range(TEX)]


def clamp(v):
    return max(0, min(255, int(round(v))))


def put(x, y, c, a=255):
    if 0 <= x < TEX and 0 <= y < TEX:
        img[y][x] = (clamp(c[0]), clamp(c[1]), clamp(c[2]), a)


def shade(c, k):
    return (c[0] * k, c[1] * k, c[2] * k)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def noisy(c, amp, r=RNG):
    n = r.uniform(-amp, amp)
    return (c[0] + n, c[1] + n * 1.05, c[2] + n * 0.8)


def fill(x0, y0, w, h, fn):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            res = fn(x - x0, y - y0)
            if len(res) == 4:
                put(x, y, res[:3], res[3])
            else:
                put(x, y, res)


OLIVE = (76, 84, 50)
OLIVE_D = (58, 64, 40)
RUST = (112, 64, 34)
RUST_L = (150, 88, 42)
DARKM = (52, 54, 52)
GLASS = (46, 60, 66)
RED = (160, 38, 32)
WHITE = (200, 198, 184)


def hull(base, rust_p=0.07, lines=True, seed=0):
    r = random.Random(seed)
    spots = set()
    for _ in range(int(256 * rust_p)):
        sx, sy = r.randrange(16), r.randrange(16)
        spots.add((sx, sy))
        if r.random() < 0.5:
            spots.add((sx, min(15, sy + 1)))  # потёки ржавчины вниз

    def f(x, y):
        c = noisy(base, 7, r)
        if lines and (x == 7 or y == 10):
            c = shade(c, 0.78)  # швы панелей
        if lines and (x in (6, 8)) and y % 3 == 1:
            c = shade(c, 1.2)  # заклёпки
        if (x, y) in spots:
            c = mix(c, RUST if r.random() < 0.6 else RUST_L, 0.8)
        return c
    return f


# (0,0) корпус A, (16,0) корпус B (камуфляж), (32,0) ржавчина, (48,0) тёмный металл
fill(0, 0, 16, 16, hull(OLIVE, 0.06, True, 1))
_rb = random.Random(2)
_blob = [(_rb.randrange(16), _rb.randrange(16), _rb.uniform(2, 4.5)) for _ in range(4)]


def camo(x, y):
    c = noisy(OLIVE, 6, _rb)
    for bx, by, br in _blob:
        if (x - bx) ** 2 + (y - by) ** 2 < br * br:
            c = noisy(OLIVE_D, 6, _rb)
    if _rb.random() < 0.05:
        c = mix(c, RUST, 0.7)
    if y == 5:
        c = shade(c, 0.8)
    return c


fill(16, 0, 16, 16, camo)
fill(32, 0, 16, 16, lambda x, y: noisy(mix(RUST, RUST_L, RNG.random() * 0.6), 12)
     if RNG.random() > 0.12 else noisy(OLIVE_D, 6))
fill(48, 0, 16, 16, lambda x, y: shade(noisy(DARKM, 6), 0.8 if (x % 8 == 0 or y % 8 == 0) else 1))


# (0,16) стекло кабины 16x16 (полупрозрачное, рама, трещины)
def glass(x, y):
    if x in (0, 15) or y in (0, 15) or x == 8:
        return noisy(OLIVE_D, 5) + (255,)
    c = noisy(GLASS, 5)
    if 2 <= (x + y) - 8 <= 3:
        c = mix(c, (150, 170, 175), 0.45)  # блик
    if (x, y) in {(3, 4), (4, 5), (5, 5), (5, 6), (6, 8), (4, 6), (11, 3), (12, 4), (12, 5), (13, 5)}:
        return (170, 176, 170, 230)  # трещины
    if RNG.random() < 0.04:
        return mix(c, (90, 80, 60), 0.6) + (220,)  # грязь
    return c + (150,)


fill(0, 16, 16, 16, glass)


# (16,16) иллюминатор 8x8
def porthole(x, y):
    d = math.hypot(x - 3.5, y - 3.5)
    if d < 2.4:
        c = noisy(GLASS, 4)
        return mix(c, (140, 160, 165), 0.5) if x - y == -1 else c
    if d < 3.4:
        return noisy((40, 42, 38), 4)  # резиновый уплотнитель
    return noisy(OLIVE, 6)


fill(16, 16, 8, 8, porthole)

STAR = ["...##...",
        "...##...",
        "########",
        ".######.",
        "..####..",
        ".##..##.",
        "##....##",
        "........"]


def star(x, y):
    if STAR[y][x] == "#":
        return mix(noisy(RED, 10), OLIVE, 0.35) if RNG.random() < 0.2 else noisy(RED, 10)
    return noisy(OLIVE, 6)


fill(24, 16, 8, 8, star)

DIG = {
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
}


def number(x, y):
    c = noisy(OLIVE, 6)
    for i, d in enumerate("32"):
        ox = 2 + i * 7
        if 0 <= x - ox < 5 and 0 <= y - 0 < 7 and DIG[d][y][x - ox] == "1":
            c = noisy(WHITE, 10)
            if RNG.random() < 0.15:
                c = mix(c, OLIVE, 0.6)  # облезшая краска
    return c


fill(16, 24, 16, 8, number)
# (32,16) шина, (40,16) лопасть, (48,16) пол, (56,16) стенка салона
fill(32, 16, 8, 8, lambda x, y: noisy((26, 26, 25), 4) if (x + y) % 3 else noisy((40, 40, 38), 3))
fill(40, 16, 8, 8, lambda x, y: noisy((66, 70, 58), 5))
fill(48, 16, 8, 8, lambda x, y: noisy((70, 70, 66), 5) if (x + 2 * y) % 4 == 0 else noisy((52, 52, 50), 4))
fill(56, 16, 8, 8, lambda x, y: mix(noisy((96, 108, 94), 6), (70, 62, 48), 0.45 if RNG.random() < 0.15 else 0))
# (32,24) брезент сидений, (40,24) приборная панель, (48,24) ящик, (56,24) копоть
fill(32, 24, 8, 8, lambda x, y: shade(noisy((112, 72, 46), 7), 0.75 if x in (0, 4) else 1))
_dials = {(1, 1), (2, 1), (4, 1), (5, 1), (1, 4), (2, 4), (5, 4), (6, 4)}


def panel(x, y):
    if (x, y) in _dials:
        return (190, 190, 170)
    if (x - 1, y) in _dials:
        return (90, 150, 90)
    if y == 6 and x % 2 == 0:
        return (160, 50, 40)  # тумблеры
    return noisy((22, 24, 22), 3)


fill(40, 24, 8, 8, panel)
fill(48, 24, 8, 8, lambda x, y: shade(noisy((122, 92, 56), 8), 0.7 if y in (0, 3, 7) or x in (0, 7) else 1))
fill(56, 24, 8, 8, lambda x, y: noisy((30, 28, 26), 5))


# (0,32) боковая сдвижная дверь 16x16
def door(x, y):
    if x in (0, 15) or y in (0, 15):
        return shade(noisy(OLIVE, 5), 0.7)
    d = math.hypot(x - 7.5, y - 4.5)
    if d < 2.4:
        return noisy(GLASS, 4)
    if d < 3.2:
        return (40, 42, 38)
    if y == 9 and 11 <= x <= 13:
        return (140, 140, 132)  # ручка
    return hull(OLIVE, 0.05, False, 3)(x, y)


fill(0, 32, 16, 16, door)
fill(16, 32, 16, 16, lambda x, y: mix(noisy((100, 108, 90), 6), (70, 60, 40), 0.5 if RNG.random() < 0.08 else 0))
fill(32, 32, 16, 16, lambda x, y: shade(camo(x, y), 0.7) if x in (0, 15) or y % 5 == 0 else camo(x, y))
# (48,32) предупреждающая полоса, (56,32) ящик с патронами, (48,40) красный, (56,40) хром
fill(48, 32, 8, 8, lambda x, y: (190, 40, 30) if ((x + y) // 2) % 2 == 0 else (215, 210, 196))
fill(56, 32, 8, 8, lambda x, y: (190, 170, 60) if y == 3 and 1 <= x <= 6 else shade(noisy((80, 86, 50), 6), 0.7 if x in (0, 7) else 1))
fill(48, 40, 8, 8, lambda x, y: (220, 210, 200) if (x in (3, 4) and 1 <= y <= 6) or (y in (3, 4) and 1 <= x <= 6) else noisy(RED, 10))
fill(56, 40, 8, 8, lambda x, y: noisy((150, 150, 144), 10))
# (0,48) полоса лопасти 64x4
fill(0, 48, 64, 4, lambda x, y: shade(noisy((72, 76, 62), 5), 0.75 if y in (0, 3) else (1.1 if x % 12 == 0 else 1)))
# (0,52) решётка, (16,52) кожа, (32,52) мох/грязь, (48,52) кабели/разное
fill(0, 52, 16, 12, lambda x, y: (18, 18, 17) if x % 3 == 0 or y % 3 == 0 else noisy((46, 48, 44), 4))
fill(16, 52, 16, 12, lambda x, y: noisy((56, 44, 36), 6))
fill(32, 52, 16, 12, lambda x, y: noisy((70, 82, 38), 10) if RNG.random() < 0.6 else noisy((82, 66, 44), 8))
fill(48, 52, 16, 12, lambda x, y: noisy((36, 44, 34), 6) if (x + y) % 4 else (20, 20, 20))

MAT = {  # имя: (u, v, w, h, растягивать_целиком)
    "hull": (0, 0, 16, 16, False),
    "camo": (16, 0, 16, 16, False),
    "rust": (32, 0, 16, 16, False),
    "metal": (48, 0, 16, 16, False),
    "glass": (0, 16, 16, 16, True),
    "porthole": (16, 16, 8, 8, True),
    "star": (24, 16, 8, 8, True),
    "number": (16, 24, 16, 8, True),
    "tire": (32, 16, 8, 8, False),
    "blade": (40, 16, 8, 8, False),
    "floor": (48, 16, 8, 8, False),
    "wall": (56, 16, 8, 8, False),
    "canvas": (32, 24, 8, 8, True),
    "panel": (40, 24, 8, 8, True),
    "crate": (48, 24, 8, 8, True),
    "soot": (56, 24, 8, 8, False),
    "door": (0, 32, 16, 16, True),
    "belly": (16, 32, 16, 16, False),
    "rear": (32, 32, 16, 16, True),
    "warn": (48, 32, 8, 8, True),
    "ammo": (56, 32, 8, 8, True),
    "red": (48, 40, 8, 8, True),
    "chrome": (56, 40, 8, 8, False),
    "bladestrip": (0, 48, 64, 4, True),
    "grille": (0, 52, 16, 12, True),
    "leather": (16, 52, 16, 12, False),
    "moss": (32, 52, 16, 12, False),
    "cable": (48, 52, 16, 12, False),
}


def png_bytes():
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in img)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", TEX, TEX, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------------------
# Геометрия. Единицы Blockbench (16 = 1 блок). Нос смотрит на север (-Z).
# ---------------------------------------------------------------------------
elements = []
FACE_AXES = {  # грань: (ось u, ось v)
    "north": (0, 1), "south": (0, 1), "east": (2, 1), "west": (2, 1), "up": (0, 2), "down": (0, 2),
}


def face_uv(mat, size, face):
    u, v, w, h, whole = MAT[mat]
    if whole:
        return [u, v, u + w, v + h]
    au, av = FACE_AXES[face]
    fw = max(1.0, min(w, size[au] * 0.5))
    fh = max(1.0, min(h, size[av] * 0.5))
    ou = RNG.uniform(0, w - fw)
    ov = RNG.uniform(0, h - fh)
    q = lambda n: round(n * 4) / 4
    return [q(u + ou), q(v + ov), q(u + ou + fw), q(v + ov + fh)]


def cube(name, frm, to, mat="hull", faces=None, origin=None, rot=None):
    faces = faces or {}
    frm, to = [round(min(a, b), 4) for a, b in zip(frm, to)], [max(a, b) for a, b in zip(frm, to)]
    to_ = [round(max(a, b), 4) for a, b in zip(frm, to)]
    size = [t - f for f, t in zip(frm, to_)]
    el = {
        "name": name, "box_uv": False, "rescale": False, "locked": False,
        "render_order": "default", "allow_mirror_modeling": True,
        "from": frm, "to": to_, "autouv": 0, "color": RNG.randrange(8),
        "origin": origin or [round((f + t) / 2, 4) for f, t in zip(frm, to_)],
        "faces": {f: {"uv": face_uv(faces.get(f, mat), size, f), "texture": 0}
                  for f in ("north", "east", "south", "west", "up", "down")},
        "type": "cube", "uuid": new_uuid(),
    }
    if rot and any(rot):
        el["rotation"] = rot
    elements.append(el)
    return el["uuid"]


def mirror_x(frm, to):
    return [-to[0], frm[1], frm[2]], [-frm[0], to[1], to[2]]


def pair(name, frm, to, mat="hull", faces=None, origin=None, rot=None):
    """Левый (x<0) и правый зеркальный кубы. Грани east/west меняются местами."""
    faces = faces or {}
    a = cube(name + "_L", frm, to, mat, faces, origin, rot)
    mf, mt = mirror_x(frm, to)
    swap = {"east": "west", "west": "east"}
    mfaces = {swap.get(k, k): v for k, v in faces.items()}
    mo = [-origin[0], origin[1], origin[2]] if origin else None
    mr = [rot[0], -rot[1], -rot[2]] if rot else None
    b = cube(name + "_R", mf, mt, mat, mfaces, mo, mr)
    return [a, b]


def group(name, origin, children, rotation=None):
    g = {"name": name, "origin": origin, "color": 0, "uuid": new_uuid(), "export": True,
         "mirror_uv": False, "isOpen": False, "locked": False, "visibility": True,
         "autouv": 0, "children": children}
    if rotation:
        g["rotation"] = rotation
    return g


IN = {"east": "wall"}   # внутренняя грань левой стены
IN_R = {"west": "wall"}

# --- Фюзеляж (грузовая кабина): x -11..11, y 6..28, z -26..24 ---
fus = []
fus.append(cube("floor", [-11, 6, -26], [11, 7, 24], "hull", {"up": "floor", "down": "belly"}))
fus.append(cube("floor_sill", [-11, 6, 24], [11, 7, 30], "hull", {"up": "floor", "down": "belly"}))
fus.append(cube("belly_step", [-10, 5, -26], [10, 6, 24], "belly"))
fus.append(cube("roof", [-11, 27, -26], [11, 28, 24], "hull", {"down": "wall"}))
fus.append(cube("roof_crown", [-9, 28, -26], [9, 29, 24], "camo"))
fus.append(cube("wall_L_front", [-11, 7, -26], [-10, 27, -24], "hull", IN))
fus.append(cube("wall_L_overdoor", [-11, 24, -24], [-10, 27, -15], "hull", IN))
fus.append(cube("wall_L_rear", [-11, 7, -15], [-10, 27, 24], "camo", IN))
fus.append(cube("wall_R", [10, 7, -26], [11, 27, 24], "camo", IN_R))
fus += pair("chine_low", [-11.6, 6, -26], [-11, 8, 24], "belly")
fus += pair("chine_top", [-11.4, 26, -26], [-10.4, 28.4, 24], "hull", origin=[-11, 27, 0], rot=[0, 0, -40])
fus.append(cube("bulkhead_L", [-11, 7, -27], [-3, 27, -26], "wall", {"north": "wall"}))
fus.append(cube("bulkhead_R", [3, 7, -27], [11, 27, -26], "wall"))
fus.append(cube("bulkhead_top", [-3, 23, -27], [3, 27, -26], "wall"))
# Задняя часть над створками и переход в хвостовую балку
fus.append(cube("rear_fairing", [-10, 20, 24], [10, 28, 32], "camo", {"down": "wall"}))
fus.append(cube("rear_fairing_top", [-8, 28, 24], [8, 29, 30], "camo"))
fus += pair("porthole", [-11.3, 17, -12], [-11, 21, -8], "porthole")
for i, zc in enumerate([-3, 4, 11, 18]):
    fus.append(cube(f"porthole_L{i}", [-11.3, 17, zc - 2], [-11, 21, zc + 2], "porthole"))
for i, zc in enumerate([-21, -14, -3, 4, 11, 18]):
    fus.append(cube(f"porthole_R{i}", [11, 17, zc - 2], [11.3, 21, zc + 2], "porthole"))
# внутренние «окна» иллюминаторов
for zc in [-10, -3, 4, 11, 18]:
    fus.append(cube("porthole_in_L", [-10, 17, zc - 2], [-9.8, 21, zc + 2], "porthole"))
for zc in [-21, -14, -10, -3, 4, 11, 18]:
    fus.append(cube("porthole_in_R", [9.8, 17, zc - 2], [10, 21, zc + 2], "porthole"))
fus.append(cube("door_rail", [-12.6, 24.2, -24], [-11, 25, -4], "metal"))
fus.append(cube("door_step", [-13, 4.5, -23], [-11, 5.3, -16], "metal"))
fus.append(cube("hoist_arm", [-15, 25, -23], [-11, 26, -21], "metal"))
fus.append(cube("hoist_winch", [-16, 23.5, -23.5], [-14, 26, -20.5], "metal"))
fus += pair("pitot", [-6.2, 12, -52], [-5.8, 12.4, -44], "chrome")
fus.append(cube("antenna_top", [-0.3, 29, -6], [0.3, 33, -5], "metal"))
fus.append(cube("antenna_belly", [-0.3, 2, 10], [0.3, 5, 11], "metal"))
fus.append(cube("beacon_red", [-0.8, 29, 18], [0.8, 30, 19.6], "red"))

# --- Кабина пилотов и нос ---
ck = []
ck.append(cube("cockpit_floor", [-10, 6, -40], [10, 7, -27], "hull", {"up": "floor", "down": "belly"}))
ck += pair("cockpit_wall_low", [-10, 7, -38], [-9, 16, -27], "hull", IN)
ck += pair("cockpit_blister", [-10.4, 16, -36], [-9.4, 25, -28], "glass")
ck += pair("cockpit_pillar", [-10.4, 16, -28], [-9, 27, -27], "hull")
ck += pair("cockpit_pillar_front", [-10.4, 16, -37], [-9, 26, -36], "hull")
ck.append(cube("cockpit_roof", [-10, 25, -35], [10, 27, -27], "hull", {"down": "wall"}))
ck.append(cube("windscreen", [-9, 15, -39.5], [9, 26, -38.9], "glass", origin=[0, 15, -39], rot=[30, 0, 0]))
ck.append(cube("windscreen_bar", [-0.5, 15, -39.8], [0.5, 26, -38.8], "hull", origin=[0, 15, -39], rot=[30, 0, 0]))
ck += pair("windscreen_side", [-10, 15, -39.5], [-9, 26, -36.5], "glass", origin=[-9.5, 15, -39], rot=[30, 0, 0])
ck.append(cube("nose_box", [-8, 6, -44], [8, 14, -38], "hull", {"down": "belly"}))
ck.append(cube("nose_top", [-8, 14, -43], [8, 15.4, -38], "camo"))
ck.append(cube("nose_tip", [-6.5, 7, -46.5], [6.5, 13.5, -44], "hull", {"north": "glass", "down": "belly"}))
ck.append(cube("chin_glass", [-7, 8, -44.3], [7, 13.4, -44], "glass"))
ck += pair("nose_side_glass", [-8.3, 8.5, -43], [-8, 13, -39], "glass")
ck.append(cube("nose_bumper", [-5, 6.2, -47], [5, 7.2, -44], "belly"))
# интерьер кабины пилотов
ck.append(cube("instrument_panel", [-8.5, 13, -38.5], [8.5, 18, -37.5], "panel",
               {"north": "metal", "up": "metal"}, origin=[0, 13, -38], rot=[-15, 0, 0]))
ck.append(cube("panel_hood", [-8.5, 18, -39], [8.5, 18.8, -36.5], "metal"))
ck.append(cube("center_console", [-1.5, 7, -38], [1.5, 12, -30], "metal", {"up": "panel"}))
ck.append(cube("overhead_panel", [-3, 24, -35], [3, 25, -29], "metal", {"down": "panel"}))
for side, x in (("L", -4.5), ("R", 4.5)):
    ck.append(cube(f"pilot_seat_base_{side}", [x - 2.2, 7, -34], [x + 2.2, 10, -30], "metal"))
    ck.append(cube(f"pilot_seat_cushion_{side}", [x - 2.4, 10, -34.5], [x + 2.4, 11, -29.5], "leather"))
    ck.append(cube(f"pilot_seat_back_{side}", [x - 2.4, 11, -30], [x + 2.4, 19, -28.8], "leather",
                   origin=[x, 11, -29.5], rot=[12, 0, 0]))
    ck.append(cube(f"pilot_headrest_{side}", [x - 1.4, 19, -29], [x + 1.4, 21, -28], "leather",
                   origin=[x, 11, -29.5], rot=[12, 0, 0]))
    ck.append(cube(f"cyclic_stick_{side}", [x - 0.3, 7, -36.3], [x + 0.3, 12.5, -35.7], "metal",
                   origin=[x, 7, -36], rot=[-10, 0, 0]))
    ck.append(cube(f"cyclic_grip_{side}", [x - 0.5, 12.3, -37.4], [x + 0.5, 13.6, -36.4], "leather"))
    ck.append(cube(f"collective_{side}", [x - (2.9 if x < 0 else -2.9) - 0.3, 8, -33],
                   [x - (2.9 if x < 0 else -2.9) + 0.3, 8.6, -28], "metal", origin=[x, 8, -28], rot=[-20, 0, 0]))
    ck.append(cube(f"pedals_{side}", [x - 1.8, 7, -38.4], [x + 1.8, 8.2, -37.8], "metal"))
ck.append(cube("engineer_seat", [-2, 13, -27.9], [2, 13.8, -25.8], "canvas"))
ck.append(cube("radio_rack", [5, 7, -28.5], [9, 16, -27], "metal", {"south": "panel"}))

# --- Интерьер грузовой кабины ---
cab = []
cab.append(cube("bench_L_seat", [-10, 12, -12], [-6, 13, 21], "canvas"))
cab.append(cube("bench_L_back", [-10, 14, -12], [-9.4, 21, 21], "canvas"))
cab.append(cube("bench_R_seat", [6, 12, -24], [10, 13, 21], "canvas"))
cab.append(cube("bench_R_back", [9.4, 14, -24], [10, 21, 21], "canvas"))
for z in range(-10, 22, 8):
    cab.append(cube("bench_L_leg", [-7, 7, z], [-6.4, 12, z + 0.6], "chrome"))
for z in range(-22, 22, 8):
    cab.append(cube("bench_R_leg", [6.4, 7, z], [7, 12, z + 0.6], "chrome"))
cab += pair("roof_handrail", [-6, 25, -24], [-5.5, 25.5, 22], "chrome")
cab += pair("floor_rail", [-4.5, 7, -25], [-3.5, 7.3, 23], "metal")
for z in (-18, -2, 14):
    cab.append(cube("cabin_lamp", [-1, 26.2, z], [1, 27, z + 2], "chrome"))
cab.append(cube("cable_run", [-9.8, 25.5, -25], [-9.2, 26.5, 23], "cable"))
cab.append(cube("heater_duct", [8, 23.5, -25], [9.8, 25.5, 23], "metal"))
cab.append(cube("aux_fuel_tank", [1, 7, -24], [6, 13, -16], "hull", {"up": "metal"}))
cab.append(cube("aux_fuel_tank_strap", [0.8, 7, -20.5], [6.2, 13.2, -19.5], "metal"))
cab.append(cube("crate_big", [-6, 7, 12], [0, 13, 20], "crate"))
cab.append(cube("crate_small", [-5, 13, 14], [-1, 17, 18], "crate", origin=[-3, 13, 16], rot=[0, 15, 0]))
cab.append(cube("ammo_box_1", [1.5, 7, 16], [5.5, 10, 22], "ammo"))
cab.append(cube("ammo_box_2", [2, 10, 17], [5, 12.5, 21], "ammo", origin=[3.5, 10, 19], rot=[0, -20, 0]))
cab.append(cube("ammo_box_open", [-8, 7, -6], [-4, 9.5, -2], "ammo", {"up": "soot"}))
cab.append(cube("fire_extinguisher", [7, 7, -25.6], [8.6, 13, -24.2], "red"))
cab.append(cube("first_aid", [9.2, 20, -12], [10, 23, -8], "red"))
cab.append(cube("stretcher", [-2, 7.3, -8], [3, 7.9, 8], "canvas", origin=[0, 7, 0], rot=[0, 10, 0]))
cab.append(cube("helmet", [-8.6, 13, 2], [-7, 14.2, 3.6], "hull"))
cab.append(cube("moss_patch_floor", [-10, 7, 19], [-5, 7.2, 24], "moss"))
cab.append(cube("debris_panel", [3, 7, -4], [7, 7.4, 1], "rust", origin=[5, 7, -1.5], rot=[0, 30, 8]))

# --- Двигатели и редуктор ---
eng = []
eng.append(cube("engine_housing", [-8, 28, -35], [8, 35, 4], "camo", {"north": "grille"}))
eng.append(cube("engine_top", [-7, 35, -33], [7, 36, 2], "hull"))
eng += pair("engine_side_bevel", [-8.8, 29, -35], [-7.8, 34, 4], "hull", origin=[-8, 34, 0], rot=[0, 0, 20])
eng.append(cube("engine_front_slope", [-8, 27, -38], [8, 28.5, -34], "hull"))
eng.append(cube("engine_tail_1", [-6, 28, 4], [6, 33, 14], "camo"))
eng.append(cube("engine_tail_2", [-4, 28, 14], [4, 30.5, 24], "camo"))
for side, xc in (("L", -4.5), ("R", 4.5)):
    eng.append(cube(f"intake_{side}", [xc - 3, 28.5, -39], [xc + 3, 34.5, -34], "hull", {"north": "soot"}))
    eng.append(cube(f"intake_ring_{side}", [xc - 2.6, 28.9, -38.8], [xc + 2.6, 34.1, -34], "hull",
                    {"north": "soot"}, origin=[xc, 31.5, -36], rot=[0, 0, 45]))
    eng.append(cube(f"intake_cone_{side}", [xc - 1, 30.5, -40], [xc + 1, 32.5, -38], "metal"))
eng += pair("exhaust_pipe", [-13, 29, -7], [-8, 33.5, -1], "hull", {"south": "soot", "west": "rust"},
            origin=[-8, 31, -4], rot=[0, -30, 0])
eng += pair("exhaust_soot", [-12.6, 29.4, -1.2], [-8.4, 33.1, -0.8], "soot", origin=[-8, 31, -4], rot=[0, -30, 0])
eng.append(cube("gearbox_fairing", [-5, 36, -19], [5, 38, -7], "hull"))
eng.append(cube("fan_intake", [-3, 36, -6], [3, 39, 1], "hull", {"north": "grille"}))
eng.append(cube("rotor_mast", [-1.2, 38, -14.2], [1.2, 41, -11.8], "metal"))
eng.append(cube("swashplate", [-2.2, 39.2, -15.2], [2.2, 40, -10.8], "metal"))

# --- Топливные баки ---
tanks = []
tanks.append(cube("fuel_tank_L", [-15.5, 8, -13], [-11, 14, 8], "hull", {"down": "belly"}))
tanks.append(cube("fuel_tank_L_front", [-15, 8.5, -15], [-11.5, 13.5, -13], "hull"))
tanks.append(cube("fuel_tank_L_rear", [-15, 8.5, 8], [-11.5, 13.5, 10], "hull"))
tanks.append(cube("fuel_tank_R", [11, 8, -20], [15.5, 14, 8], "hull", {"down": "belly"}))
tanks.append(cube("fuel_tank_R_front", [11.5, 8.5, -22], [15, 13.5, -20], "hull"))
tanks.append(cube("fuel_tank_R_rear", [11.5, 8.5, 8], [15, 13.5, 10], "hull"))
for z in (-8, 2):
    tanks += pair("tank_strap", [-15.7, 7.8, z], [-11, 14.2, z + 0.8], "metal")
tanks.append(cube("tank_strap_R_front", [11, 7.8, -16], [15.7, 14.2, -15.2], "metal"))

# --- Хвостовая балка ---
tail = []
boom = [(-6, 18, 32, 6, 27, 44), (-5, 19, 44, 5, 26.5, 58), (-4, 20, 58, 4, 26, 74),
        (-3, 21, 74, 3, 25.5, 90), (-2.5, 21.5, 90, 2.5, 25, 101)]
for i, b in enumerate(boom):
    tail.append(cube(f"tail_boom_{i}", b[:3], b[3:], "camo" if i % 2 else "hull", {"down": "belly"}))
tail.append(cube("boom_rear_ramp", [-8, 16, 24], [8, 22, 34], "hull", {"down": "belly"}, origin=[0, 16, 30], rot=[-25, 0, 0]))
tail.append(cube("driveshaft_cover", [-1, 26.5, 32], [1, 28, 96], "metal"))
tail += pair("stabilizer", [-12, 22, 84], [-2.5, 22.8, 91], "hull")
tail += pair("stabilizer_tip", [-12.5, 21.6, 84.5], [-12, 23.2, 90.5], "warn")
tail.append(cube("tail_skid_strut", [-0.4, 16, 90], [0.4, 21.5, 91], "metal", origin=[0, 21.5, 90.5], rot=[-20, 0, 0]))
tail.append(cube("tail_skid_pad", [-1, 15.2, 91], [1, 16.2, 94], "metal"))
tail.append(cube("tail_fin", [-1, 23, 95], [1, 42, 101], "camo", origin=[0, 24, 98], rot=[30, 0, 0]))
tail.append(cube("tail_fin_root", [-1.8, 21.5, 94], [1.8, 26, 103], "hull"))
tail.append(cube("tail_gearbox", [-1.2, 36.5, 103.5], [2, 39.5, 107.5], "metal"))
tail.append(cube("tail_light", [-0.5, 39.5, 106], [0.5, 40.3, 107], "chrome"))
tail += pair("star_boom", [-5.2, 20, 47], [-5, 26, 53], "star")
tail += pair("star_fairing", [-10.2, 21, 25], [-10, 27, 31], "star")
tail.append(cube("number_L", [-11.25, 22, 5], [-11.05, 26, 13], "number"))
tail.append(cube("number_R", [11.05, 22, 16], [11.25, 26, 24], "number"))
tail.append(cube("number_boom", [-4.2, 21, 62], [-4, 24.5, 69], "number"))

# --- Главный несущий винт (5 лопастей) ---
HUB = [0, 41, -13]
rotor_children = [
    cube("rotor_hub", [-2.6, 41, -15.6], [2.6, 43, -10.4], "metal"),
    cube("rotor_hub_cap", [-1.5, 43, -14.5], [1.5, 44.2, -11.5], "metal"),
    cube("rotor_hub_ring", [-2.2, 41.2, -15.2], [2.2, 42.8, -10.8], "metal", origin=HUB, rot=[0, 36, 0]),
]
for k in range(5):
    blade = [
        cube(f"blade{k}_cuff", [2.5, 41.2, -14.2], [9, 42.6, -11.8], "metal"),
        cube(f"blade{k}_damper", [2.5, 42.6, -13.6], [6, 43.4, -12.4], "metal"),
        cube(f"blade{k}", [9, 41.6, -15], [84, 42.2, -11], "blade", {"up": "bladestrip", "down": "bladestrip"}),
        cube(f"blade{k}_tip", [84, 41.6, -15], [88, 42.2, -11], "warn"),
    ]
    rotor_children.append(group(f"blade_{k}", HUB, blade, rotation=[0, k * 72, 0]))
main_rotor = group("main_rotor", HUB, rotor_children)

# --- Рулевой (хвостовой) винт, справа на киле, 3 лопасти ---
TR = [2.5, 38, 105.5]
tr_children = [cube("tail_rotor_hub", [2, 37, 104.5], [4, 39, 106.5], "metal"),
               cube("tail_rotor_cap", [4, 37.4, 104.9], [4.8, 38.6, 106.1], "metal")]
for k in range(3):
    tr_children.append(group(f"tr_blade_{k}", TR, [
        cube(f"tr_blade{k}", [2.8, 39, 104.9], [3.3, 51, 106.1], "blade"),
        cube(f"tr_blade{k}_tip", [2.8, 51, 104.9], [3.3, 54, 106.1], "warn"),
    ], rotation=[k * 120, 0, 0]))
tail_rotor = group("tail_rotor", TR, tr_children)
tail.append(tail_rotor)

# --- Шасси ---


def wheel(name, c, r, w):
    x0, x1 = c[0] - w / 2, c[0] + w / 2
    s = r * 0.83
    return [cube(name, [x0, c[1] - s, c[2] - s], [x1, c[1] + s, c[2] + s], "tire"),
            cube(name + "_oct", [x0, c[1] - s, c[2] - s], [x1, c[1] + s, c[2] + s], "tire",
                 origin=list(c), rot=[45, 0, 0]),
            cube(name + "_hub", [x0 - 0.2, c[1] - r * 0.4, c[2] - r * 0.4],
                 [x1 + 0.2, c[1] + r * 0.4, c[2] + r * 0.4], "chrome")]


def main_gear(sign):
    s = "L" if sign < 0 else "R"
    X = lambda a, b: (min(sign * a, sign * b), max(sign * a, sign * b))
    parts = wheel(f"wheel_main_{s}", [sign * 17, 4, 2], 4, 3)
    xa, xb = X(16.5, 17.5)
    parts.append(cube(f"oleo_{s}", [xa, 4, 1.5], [xb, 15, 2.5], "chrome"))
    xa, xb = X(11, 17.5)
    parts.append(cube(f"brace_top_{s}", [xa, 14, 1.4], [xb, 15.2, 2.6], "metal"))
    xa, xb = X(11, 16.5)
    parts.append(cube(f"brace_low_{s}", [xa, 3.6, 1.4], [xb, 4.6, 2.6], "metal"))
    parts.append(cube(f"brace_diag_{s}", [xa, 3.6, -5], [xb, 4.6, -4], "metal",
                      origin=[sign * 16.5, 4, 2], rot=[0, -sign * 38, 0]))
    return group(f"gear_main_{s}", [sign * 17, 15, 2], parts)


gear_nose = group("gear_nose", [0, 7, -38], [
    cube("nose_strut", [-0.5, 3.4, -38.5], [0.5, 7, -37.5], "chrome"),
    cube("nose_fork", [-2.6, 3.2, -38.4], [2.6, 4, -37.6], "metal"),
    *wheel("wheel_nose_L", [-1.8, 3.5, -38], 3.4, 1.8),
    *wheel("wheel_nose_R", [1.8, 3.5, -38], 3.4, 1.8),
])

# --- Двери ---
side_door = group("side_door", [-11.5, 7, -24], [
    cube("side_door_panel", [-11.2, 7, -24], [-10.2, 24, -15], "hull", {"west": "door", "east": "wall"}),
    cube("side_door_handle_in", [-10.2, 15, -16.5], [-9.8, 16, -15.6], "chrome"),
    cube("side_door_roller", [-11.6, 23.4, -23.6], [-11.2, 24.4, -22.6], "metal"),
])
cockpit_door = group("cockpit_door", [3, 7, -26.5], [
    cube("cockpit_door_panel", [-3, 7, -26.8], [3, 23, -26.2], "wall"),
    cube("cockpit_door_window", [-1.5, 17, -26.9], [1.5, 20, -26.1], "porthole"),
    cube("cockpit_door_handle", [-2.6, 14, -26.1], [-1.8, 14.6, -25.7], "chrome"),
])


def rear_door(sign):
    s = "L" if sign < 0 else "R"
    X = lambda a, b: (min(sign * a, sign * b), max(sign * a, sign * b))
    xa, xb = X(10, 11)
    side = cube(f"rear_door_side_{s}", [xa, 7, 24], [xb, 20, 29], "rear",
                {("east" if sign < 0 else "west"): "wall"})
    xa, xb = X(0, 11)
    back = cube(f"rear_door_back_{s}", [xa, 7, 29], [xb, 20, 30], "rear", {"north": "wall"})
    xa, xb = X(0.2, 10)
    bottom = cube(f"rear_door_bottom_{s}", [xa, 7, 28], [xb, 8, 29], "hull")
    xa, xb = X(1, 3)
    handle = cube(f"rear_door_handle_{s}", [xa, 12, 30], [xb, 12.6, 30.4], "chrome")
    return group(f"rear_door_{s}", [sign * 11, 7, 24], [side, back, bottom, handle])


rear_L, rear_R = rear_door(-1), rear_door(1)

# ---------------------------------------------------------------------------
# Иерархия
# ---------------------------------------------------------------------------
body = group("body", [0, 18, 0], [
    group("fuselage", [0, 18, 0], fus),
    group("cockpit", [0, 12, -34], ck),
    group("cabin_interior", [0, 12, 0], cab),
    group("engines", [0, 32, -14], eng),
    group("fuel_tanks", [0, 11, -5], tanks),
    group("tail", [0, 24, 60], tail),
    side_door, cockpit_door, rear_L, rear_R,
])
gear = group("landing_gear", [0, 6, 0], [main_gear(-1), main_gear(1), gear_nose])
root = group("helicopter", [0, 18, 0], [body, main_rotor, gear])
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
    """tracks: {bone: {channel: [(t, (x,y,z), interp?), ...]}}"""
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


def spin(axis, length, turns, t0=0.0):
    v = lambda a: tuple(a if i == axis else 0 for i in range(3))
    return [(t0, v(0)), (t0 + length, v(360 * turns))]


def ramp_spin(axis, t0, t1, max_dps, speed_up=True, start_angle=0.0, step=0.25):
    """Разгон/торможение винта с постоянным ускорением: ключи каждые step секунд."""
    pts, dur = [], t1 - t0
    a = max_dps / dur
    n = int(round(dur / step))
    for i in range(n + 1):
        t = i * step
        ang = 0.5 * a * t * t if speed_up else max_dps * t - 0.5 * a * t * t
        v = tuple(start_angle + ang if j == axis else 0 for j in range(3))
        pts.append((t0 + t, v))
    return pts


def wave(channel_axis_amp, length, n, phase=0.0, base=(0, 0, 0)):
    """Плавные колебания: channel_axis_amp = [(axis, amplitude, freq_mult)]."""
    pts = []
    for i in range(n + 1):
        t = length * i / n
        v = list(base)
        for axis, amp, fm in channel_axis_amp:
            v[axis] += amp * math.sin(2 * math.pi * fm * t / length + phase)
        pts.append((t, tuple(v), "catmullrom"))
    return pts


Z3 = (0, 0, 0)
FLY_H = 32
anims = [
    animation("rotor_idle", 1.0, "loop", {
        "main_rotor": {"rotation": spin(1, 1.0, 1)},
        "tail_rotor": {"rotation": spin(0, 1.0, 5)},
        "body": {"position": [(0, Z3), (0.05, (0, 0.06, 0)), (0.1, Z3), (0.15, (0.03, 0.04, 0)),
                              (0.2, Z3), (0.25, (0, 0.06, 0)), (0.3, Z3), (0.35, (-0.03, 0.04, 0)),
                              (0.4, Z3), (0.45, (0, 0.06, 0)), (0.5, Z3), (0.55, (0.03, 0.04, 0)),
                              (0.6, Z3), (0.65, (0, 0.06, 0)), (0.7, Z3), (0.75, (-0.03, 0.04, 0)),
                              (0.8, Z3), (0.85, (0, 0.06, 0)), (0.9, Z3), (0.95, (0.03, 0.04, 0)), (1.0, Z3)]},
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
        "landing_gear": {"position": [(0, (0, -0.6, 0))]},
    }),
    animation("fly_forward", 2.0, "loop", {
        "main_rotor": {"rotation": spin(1, 2.0, 4)},
        "tail_rotor": {"rotation": spin(0, 2.0, 16)},
        "helicopter": {"position": wave([(1, 0.8, 1)], 2.0, 8, base=(0, FLY_H, 0)),
                       "rotation": wave([(0, 1.0, 1), (2, 1.2, 1)], 2.0, 8, phase=0.7, base=(12, 0, 0))},
        "landing_gear": {"position": [(0, (0, -0.6, 0))]},
    }),
    animation("takeoff", 5.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": [(0, Z3), (1, (0, 540, 0)), (2, (0, 1260, 0)), (3, (0, 1980, 0)),
                                    (4, (0, 2700, 0)), (5, (0, 3420, 0))]},
        "tail_rotor": {"rotation": [(0, Z3), (5, (5 * 2880, 0, 0))]},
        "helicopter": {"position": [(0, Z3), (1.5, Z3, "catmullrom"), (2.2, (0, 2, 0), "catmullrom"),
                                    (3.5, (0, 16, 0), "catmullrom"), (5, (0, FLY_H, 0), "catmullrom")],
                       "rotation": [(0, Z3), (1.5, Z3, "catmullrom"), (2.2, (-3, 0, 0), "catmullrom"),
                                    (3.5, (4, 0, 0), "catmullrom"), (5, (0, 0, 0), "catmullrom")]},
        "landing_gear": {"position": [(0, Z3), (1.5, Z3), (2.2, (0, -0.6, 0))]},
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
        "landing_gear": {"position": [(0, (0, -0.6, 0)), (3.6, (0, -0.6, 0)), (3.8, (0, 0.4, 0)), (4.2, Z3)]},
    }),
    animation("side_door_open", 1.2, "hold_on_last_frame", {
        "side_door": {"position": [(0, Z3), (0.3, (1.6, 0, 0), "catmullrom"), (1.2, (1.6, 0, 9.6), "catmullrom")]},
    }),
    animation("side_door_close", 1.2, "hold_on_last_frame", {
        "side_door": {"position": [(0, (1.6, 0, 9.6)), (0.9, (1.6, 0, 0), "catmullrom"), (1.2, Z3, "catmullrom")]},
    }),
    animation("rear_doors_open", 1.6, "hold_on_last_frame", {
        "rear_door_L": {"rotation": [(0, Z3), (1.6, (0, 110, 0), "catmullrom")]},
        "rear_door_R": {"rotation": [(0, Z3), (0.2, Z3), (1.6, (0, -110, 0), "catmullrom")]},
    }),
    animation("rear_doors_close", 1.6, "hold_on_last_frame", {
        "rear_door_L": {"rotation": [(0, (0, 110, 0)), (0.2, (0, 110, 0)), (1.6, Z3, "catmullrom")]},
        "rear_door_R": {"rotation": [(0, (0, -110, 0)), (1.4, Z3, "catmullrom")]},
    }),
    animation("cockpit_door_open", 0.8, "hold_on_last_frame", {
        "cockpit_door": {"rotation": [(0, Z3), (0.8, (0, -95, 0), "catmullrom")]},
    }),
    animation("cockpit_door_close", 0.8, "hold_on_last_frame", {
        "cockpit_door": {"rotation": [(0, (0, -95, 0)), (0.8, Z3, "catmullrom")]},
    }),
    # Заброшенный вертолёт: лопасти качаются на ветру, дверь поскрипывает
    animation("abandoned_wind", 4.0, "loop", {
        "main_rotor": {"rotation": wave([(1, 4, 1)], 4.0, 8)},
        **{f"blade_{k}": {"rotation": wave([(2, 1.5, 1)], 4.0, 8, phase=k * 1.1)} for k in range(5)},
        "tail_rotor": {"rotation": wave([(0, 12, 1)], 4.0, 8, phase=0.5)},
        "side_door": {"position": wave([(2, 0.4, 2)], 4.0, 8, base=(1.6, 0, 3))},
        "rear_door_L": {"rotation": wave([(1, 3, 1)], 4.0, 8, phase=2, base=(0, 25, 0))},
    }),
    # Падение: вращение вокруг оси (отказ рулевого винта), снижение, удар
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
        "landing_gear": {"position": [(0, (0, -0.6, 0)), (3.2, (0, -0.6, 0)), (3.4, (0, 1.4, 0))]},
        **{f"blade_{k}": {"rotation": [(0, Z3), (3.3, Z3), (3.5, (0, 0, -6 - 2 * k), "catmullrom"),
                                       (4, (0, 0, -8 - 2 * k), "catmullrom")]} for k in range(5)},
    }),
]

# ---------------------------------------------------------------------------
tex_png = png_bytes()
with open(os.path.join(HERE, "mi8_texture.png"), "wb") as f:
    f.write(tex_png)

model = {
    "meta": {"format_version": "4.10", "model_format": "free", "box_uv": False},
    "name": "mi8_helicopter",
    "model_identifier": "mi8_helicopter",
    "visible_box": [8, 5, 1],
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
    json.dump(model, f, ensure_ascii=False, indent=1)
print(f"elements: {len(elements)}, groups: {len(GROUPS)}, animations: {len(anims)}")
