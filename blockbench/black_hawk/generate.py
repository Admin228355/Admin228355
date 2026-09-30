#!/usr/bin/env python3
"""Генератор Blockbench-модели «Black Hawk» — тактический транспортный вертолёт
(угловой «стелс»-корпус из граней, чёрный оружейный металл).

Создаёт:
  black_hawk.bbmodel       — проект Blockbench (Generic Model), текстура 256x256, кости, анимации;
  black_hawk_texture.png   — текстура отдельным файлом;
  ../../paper-plugin/...   — модели частей для ресурспака и описание типа для плагина.

Запуск:  python3 generate.py
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from heli_lib import *  # noqa: E402,F401,F403
import heli_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TYPE_ID = "blackhawk"
L.RNG.seed(2031)

# ---------------------------------------------------------------------------
# Текстура 1024x1024: палитра «чёрный оружейный металл»
# Раскладка атласа задаётся в координатах 256, рисуется в полном разрешении (S = 4).
# ---------------------------------------------------------------------------
L.set_tex(1024)
S = L.S
BASE = (50, 52, 56)
BASE_D = (38, 40, 44)
BASE_L = (78, 81, 86)
LINE = (18, 19, 21)
HILITE = (74, 77, 82)
STEEL = (104, 107, 112)
STENCIL = (150, 152, 150)


def gun(s, t, seed=0, panel_id=0):
    """Цвет обшивки в точке (s, t) мировых единиц: тон панели, мелкий шум, пятна, потёртости."""
    tone = (L._h(panel_id, 7, seed) - 0.5) * 10
    c = (BASE[0] + tone, BASE[1] + tone, BASE[2] + tone * 1.1)
    n = L.fbm(s * 0.08, t * 0.08, seed, 3)
    c = L.shade(c, 0.9 + n * 0.2)
    g = L.fbm(s * 0.9, t * 0.9, seed + 11, 2)
    if g > 0.7:
        c = L.mix(c, BASE_L, (g - 0.7) * 2.2)     # светлые потёртости
    return L.noisy(c, 2.2)


def tile(name, u, v, w, h, whole, fn):
    L.tile(name, u, v, w, h, whole, fn)


def glass_px(x, y):
    W = 32 * S
    band = max(0.0, 1 - abs((x + y) - W * 0.9) / (W * 0.35))
    c = L.mix((64, 86, 100), (170, 190, 200), band * 0.55)
    a = 58 + band * 50
    if L.fbm(x * 0.08, y * 0.08, 44, 3) > 0.8:
        c, a = L.mix(c, (110, 104, 90), 0.3), 95      # пыль
    return c + (int(a),)


tile("glass", 0, 128, 32, 32, False, glass_px)
tile("clear", 240, 240, 16, 16, True, lambda x, y: (0, 0, 0, 0))


def window_px(x, y):
    W, H = 16 * S, 12 * S
    if x < 3 or y < 3 or x >= W - 3 or y >= H - 3:
        return L.noisy((22, 23, 25), 2)
    if x < 5 or y < 5 or x >= W - 5 or y >= H - 5:
        return L.noisy((64, 66, 70), 3)
    c = L.noisy((40, 56, 68), 3)
    if abs((x - y) - 8) < 5:
        c = L.mix(c, (160, 180, 190), 0.45)
    return c + (225,)


tile("window", 32, 128, 16, 12, True, window_px)

DIG = {"0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
       "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"]}


def number_px(x, y):
    sc = 7
    for i, d in enumerate("01"):
        gx, gy = (x - 16 - i * 52) // sc, (y - 6) // sc
        if 0 <= gx < 5 and 0 <= gy < 7 and DIG[d][gy][gx] == "1":
            if L.fbm(x * 0.15, y * 0.15, 8, 3) > 0.72:
                return (0, 0, 0, 0)
            return L.noisy(STENCIL, 5)
    return (0, 0, 0, 0)


tile("number", 48, 128, 32, 16, True, number_px)


def emblem_px(x, y):
    px, py = (x - 63.5) / 4, (y - 63.5) / 4       # те же пропорции, что в макете 32x32
    inside = False
    if abs(px) < 3 and -12 < py < 10 and abs(px) < (py + 12) * 0.25 + 0.6:
        inside = True
    for s in (-1, 1):
        qx = px * s
        if 5 < qx < 12 and -12 < py < 4 and abs(qx - (8 + (py + 12) * -0.18)) < 2.2:
            inside = True
    if abs(py + 12.5) < 1.2 and abs(px) < 12:
        inside = True
    return L.noisy((140, 142, 144), 4) if inside else (0, 0, 0, 0)


tile("emblem", 80, 128, 32, 32, True, emblem_px)


def tire_px(x, y):
    blk = ((x // 10) + (y // 14)) % 2
    edge = (y % 14) < 2 or (x % 10) < 2
    c = (20, 20, 20) if edge else ((32, 32, 33) if blk else (27, 27, 28))
    return L.noisy(c, 2)


tile("tire", 112, 128, 32, 32, False, tire_px)
tile("tireside", 144, 128, 32, 32, False, lambda x, y: L.noisy((34, 34, 35) if (y // 6) % 4 else (40, 40, 41), 2))
tile("metal", 176, 128, 32, 32, False, lambda x, y: L.shade(L.noisy((50, 52, 56), 2),
                                                          0.9 + L.fbm(x * 0.02, y * 0.4, 5, 2) * 0.2))


def hull_tile_px(x, y):
    if x % 64 in (0, 1) or y % 64 in (0, 1):
        return LINE
    if x % 64 == 2 or y % 64 == 2:
        return HILITE
    if (x % 64 == 5 or y % 64 == 5) and ((x + y) % 8 == 0):
        return (96, 98, 102)
    return gun(x * 0.25, y * 0.25, 2, (x // 64) * 7 + y // 64)


tile("hull", 208, 128, 32, 32, False, hull_tile_px)
tile("steel", 240, 128, 16, 32, False, lambda x, y: L.shade(L.noisy(STEEL, 5), 0.9 + L.fbm(x * 0.03, y * 0.5, 6, 2) * 0.2))


def floor_px(x, y):
    # рифлёный настил с поперечными швами и направляющими
    if y % 64 < 2:
        return (14, 14, 15)
    if x % 128 in range(60, 68):
        return L.noisy((78, 80, 84), 4) if x % 128 in (61, 66) else L.noisy((30, 31, 33), 2)
    d = ((x + (y // 8) * 4) % 8, y % 8)
    if d[0] in (2, 3, 4) and d[1] in (3, 4):
        return L.noisy((70, 72, 76), 3)          # рифление
    return L.noisy((40, 41, 44), 2)


tile("floor", 0, 160, 32, 32, False, floor_px)


def wall_px(x, y):
    if x % 32 < 3:
        return L.noisy((34, 35, 38), 2) if x % 32 else (22, 22, 24)   # рёбра шпангоутов
    if x % 32 == 3:
        return (78, 80, 84)
    if (y % 24 in (6, 18)) and (x % 32 in (8, 24)):
        return (96, 98, 102)                     # болты
    q = ((x // 8) + (y // 8)) % 2                # стёганая шумоизоляция
    c = (58, 60, 64) if q else (52, 54, 58)
    if x % 8 == 0 or y % 8 == 0:
        c = (44, 45, 48)
    return L.noisy(c, 2)


tile("wall", 32, 160, 32, 32, False, wall_px)


def seat_px(x, y):
    c = (34, 34, 36) if (x + y) % 3 else (28, 28, 30)
    if y % 24 in (0, 1):
        c = (58, 58, 60)                         # строчка
    if 50 <= x % 128 <= 58:
        c = (22, 22, 24) if x % 128 not in (50, 58) else (70, 70, 72)   # ремень
    return L.noisy(c, 2)


tile("seat", 64, 160, 32, 32, False, seat_px)
tile("seatframe", 96, 160, 32, 32, False, lambda x, y: L.noisy((82, 84, 88), 5))


def panel_px(x, y):
    # три МФД-экрана: карта, радар, авиагоризонт; кнопки по краям
    for i, sx in enumerate((4, 46, 88)):
        if sx <= x < sx + 36 and 8 <= y < 52:
            lx, ly = x - sx, y - 8
            if lx < 3 or ly < 3 or lx >= 33 or ly >= 41:
                return (64, 66, 70)
            cx, cy = 18, 22
            if i == 0:          # карта
                c = (18, 40, 30)
                if L.fbm(lx * 0.15, ly * 0.15, 71, 2) > 0.55:
                    c = (40, 90, 60)
                if abs(lx - ly) < 1 or abs(lx + ly - 38) < 1:
                    c = (220, 200, 90)
                return c
            if i == 1:          # радар
                d = math.hypot(lx - cx, ly - cy)
                if any(abs(d - r) < 0.7 for r in (5, 10, 15)) or abs(lx - cx) < 0.6 or abs(ly - cy) < 0.6:
                    return (90, 220, 240)
                if abs(math.atan2(ly - cy, lx - cx) - 0.8) < 0.15 and d < 15:
                    return (60, 170, 200)
                return (10, 30, 44)
            # авиагоризонт
            c = (40, 110, 170) if ly < cy + (lx - cx) * 0.15 else (120, 80, 40)
            if abs(ly - cy) < 0.7 and 8 < lx < 28:
                return (240, 240, 240)
            return c
    if y >= 56:
        if (x % 10 in (3, 4, 5)) and (y % 10 in (3, 4, 5)):
            return (80, 82, 86) if (x // 10 + y // 10) % 5 else (200, 60, 50)
        if y in (100, 101) and x % 6 < 3:
            return (220, 180, 60)
    if y < 56 and (x < 4 or x >= 124) and y % 8 in (2, 3, 4):
        return (90, 92, 96)                      # кнопки у экранов
    return L.noisy((24, 25, 27), 2)


tile("panel", 128, 160, 32, 32, True, panel_px)


def crate_px(x, y):
    W = 128
    if x < 4 or y < 4 or x >= W - 4 or y >= W - 4:
        return (26, 28, 26)
    if 60 <= x <= 67:
        return L.noisy((34, 38, 33), 2)          # ребро жёсткости
    if y in range(18, 26) and (x in range(16, 30) or x in range(98, 112)):
        return L.noisy((190, 160, 60), 6)        # защёлки
    return L.noisy((52, 58, 50), 3)


def crate_tile():
    tile("crate", 160, 160, 32, 32, True, crate_px)
    L.stencil(160 * S + 20, 160 * S + 80, "CARGO", (170, 170, 150), scale=3)


crate_tile()
tile("soot", 192, 160, 32, 16, False, lambda x, y: L.noisy((22, 21, 20), 3))
tile("light", 192, 176, 32, 16, True, lambda x, y: L.mix((255, 250, 235), (170, 175, 180),
                                                         min(1, abs(y - 32) / 30)) if 4 <= x < 124 and 6 <= y < 58 else (60, 62, 66))
tile("grille", 224, 160, 32, 32, True, lambda x, y: (10, 10, 11) if x % 6 < 2 or y % 6 < 2 else L.noisy((46, 48, 52), 3))
tile("red", 0, 192, 16, 16, False, lambda x, y: L.noisy((200, 30, 30), 10))
tile("green", 16, 192, 16, 16, False, lambda x, y: L.noisy((40, 200, 80), 10))


def lens_px(x, y):
    d = math.hypot(x - 31.5, y - 31.5)
    if d < 10:
        return (170, 235, 255) if d > 4 or (x + y) % 3 else (230, 250, 255)
    if d < 24:
        return L.mix((50, 140, 230), (20, 50, 90), (d - 10) / 14)
    return (26, 28, 30)


tile("blue", 32, 192, 16, 16, True, lens_px)


def rocket_px(x, y):
    for cx in (22, 64, 106):
        for cy in (22, 64, 106):
            d = math.hypot(x + .5 - cx, y + .5 - cy)
            if d < 14:
                return (6, 6, 6) if d < 10 else ((96, 98, 102) if d < 12 else (60, 62, 66))
    return L.noisy((40, 42, 46), 3)


tile("rocket", 48, 192, 32, 32, True, rocket_px)
tile("bladestrip", 96, 192, 128, 8, True, lambda x, y: (L.noisy((140, 142, 145), 4) if x > 480 else
                                                       L.shade(L.noisy((40, 42, 45), 2), 0.7 if y < 3 or y > 28 else (1.15 if y < 7 else 1))))
tile("bladeedge", 96, 200, 128, 8, False, lambda x, y: L.noisy((38, 40, 43), 2))
tile("tip", 96, 208, 16, 16, False, lambda x, y: L.noisy((140, 142, 145), 4))
tile("interior_dark", 112, 208, 32, 16, False, lambda x, y: L.noisy((28, 29, 31), 2))
tile("leather", 144, 208, 32, 16, False, lambda x, y: L.noisy((36, 34, 32), 2))

# ---------------------------------------------------------------------------
# Профиль корпуса: гранёное сечение из 10 вершин
#   (z, w — полуширина по «поясу», tw — полуширина крыши, bw — полуширина днища,
#    yb — днище, ybl/ybh — низ/верх вертикального борта, yt — крыша)
# ---------------------------------------------------------------------------
ST = [
    (-62, 1.5, 1.0, 1.0, 11.0, 11.5, 12.5, 13.0),
    (-60, 4.0, 2.5, 3.0, 8.5, 10.5, 13.0, 14.5),
    (-56, 7.0, 4.0, 5.0, 6.5, 9.5, 13.5, 16.5),
    (-50, 9.5, 5.0, 7.0, 5.5, 9.0, 14.5, 20.0),
    (-45, 10.8, 5.5, 8.0, 5.0, 9.0, 15.5, 24.0),
    (-40, 11.6, 6.0, 8.8, 5.0, 9.0, 16.5, 27.5),
    (-34, 12.0, 6.2, 9.2, 5.0, 9.0, 16.2, 29.5),
    (-28, 12.2, 6.2, 9.4, 5.0, 9.0, 16.2, 30.2),
    (18, 12.2, 6.2, 9.4, 5.0, 9.0, 16.2, 30.2),
    (24, 12.0, 6.2, 9.2, 5.6, 9.4, 16.4, 30.2),
    (30, 11.0, 6.8, 8.2, 8.8, 11.2, 18.2, 30.0),
    (36, 8.6, 5.4, 5.8, 13.8, 15.6, 20.2, 29.2),
    (42, 6.0, 3.8, 3.6, 17.8, 19.0, 22.2, 28.0),
    (50, 4.8, 3.2, 3.0, 19.0, 20.0, 22.8, 27.2),
    (75, 3.8, 2.6, 2.4, 20.0, 20.8, 23.2, 26.4),
    (100, 3.0, 2.0, 1.8, 20.8, 21.4, 23.6, 25.8),
    (106, 2.4, 1.6, 1.4, 21.2, 21.8, 23.6, 25.4),
]
_zs = [s[0] for s in ST]
_fn = [pchip(_zs, [s[j] for s in ST]) for j in range(1, 8)]


def prof(z):
    return tuple(f(z) for f in _fn)


def ring(z):
    w, tw, bw, yb, ybl, ybh, yt = prof(z)
    return [(0, yt, z), (tw, yt, z), (w, ybh, z), (w, ybl, z), (bw, yb, z),
            (0, yb, z), (-bw, yb, z), (-w, ybl, z), (-w, ybh, z), (-tw, yt, z)]


def halfwidth(z, y):
    """Полуширина сечения на высоте y (по правому контуру)."""
    pts = ring(z)[0:6]
    best = 0.0
    for (x0, y0, _), (x1, y1, _) in zip(pts, pts[1:]):
        lo, hi = min(y0, y1), max(y0, y1)
        if lo - 1e-6 <= y <= hi + 1e-6:
            t = 0 if abs(y1 - y0) < 1e-9 else (y - y0) / (y1 - y0)
            best = max(best, x0 + (x1 - x0) * t)
    return best


NSEG = 10
Z_RINGS = [-62, -61, -60, -58, -56, -53, -50, -47.5, -45, -42.5, -40, -37, -34, -31, -28, -24, -20, -16, -12,
           -8, -4, 0, 4, 8, 12, 16, 18, 21, 24, 27, 30, 33, 36, 39, 42, 46, 50, 56, 62, 68, 75, 82, 89, 95,
           100, 103, 106]
Z_SPLIT = 42
REG_A = (0, 0, 128 * S, 128 * S, -62, Z_SPLIT)
REG_B = (128 * S, 0, 64 * S, 128 * S, Z_SPLIT, 106)
HULL_T = 0.6
GLASS_T = 0.15
UW = [0, 0.09, 0.21, 0.31, 0.41, 0.5, 0.59, 0.69, 0.79, 0.91, 1.0]  # доли развёртки по граням

fus, side_l, side_r, ramp = [], [], [], []
DOOR_CELLS = {"side_l": set(), "side_r": set(), "ramp": set()}


def hull_uv(i, k):
    z0, z1 = Z_RINGS[i], Z_RINGS[i + 1]
    reg = REG_A if z1 <= Z_SPLIT + 1e-6 else REG_B
    u0, v0, w, h, za, zb = reg
    fv = lambda zz: v0 + h * (zz - za) / (zb - za)
    return [u0 + w * UW[k], fv(z0), u0 + w * UW[k + 1], fv(z1)]


def is_glass(k, c):
    x, y, z = c
    if -58 <= z <= -34 and k in (0, 1, 8, 9):
        return not (-45.5 <= z <= -44.5)
    if -47.5 <= z <= -37 and k in (2, 7):
        return True
    return False


def hull_dest(i, k, c):
    x, y, z = c
    if -24 < z < -12 and k in (1, 2, 3, 6, 7, 8):
        DOOR_CELLS["side_r" if x > 0 else "side_l"].add((i, k))
        return side_r if x > 0 else side_l
    if 21 < z < Z_SPLIT and y < 17.8:
        DOOR_CELLS["ramp"].add((i, k))
        return ramp
    return fus


def hull_outer(i, k, c):
    return "glass" if is_glass(k, c) else hull_uv(i, k)


def hull_inner(i, k, c):
    if is_glass(k, c):
        return "clear"      # изнутри стекло полностью прозрачное — пилоту всё видно
    if k in (4, 5) and c[2] < 42:
        return "floor"
    return "wall" if c[2] < 40 else "interior_dark"


rings = [ring(z) for z in Z_RINGS]
centers = [(0, (prof(z)[3] + prof(z)[6]) / 2, z) for z in Z_RINGS]
loft("hull", rings, centers, lambda i, k, c: GLASS_T if is_glass(k, c) else HULL_T, hull_outer, hull_dest,
     inner=hull_inner, edge=lambda i, k, c: "clear" if is_glass(k, c) else "hull")
fus.extend(disc("nose_cap", (0, 12.2, -62.1), (0, 0, 1), 1.1, 0.3, "hull"))
fus.extend(disc("tail_cap", (0, 23.4, 106.1), (0, 0, 1), 1.8, 0.3, "hull"))

# --- роспись развёрток (всё в мировых координатах, линии — в пикселях)
PANEL_Z = [-50, -34, -28, -24, -12, 0, 12, 21, 30, 42, 56, 75, 95]


def region_of(z):
    return REG_A if z <= Z_SPLIT else REG_B


def to_px(k, t, z):
    u0, v0, w, h, za, zb = region_of(z)
    return (int(u0 + w * (UW[k] + t * (UW[k + 1] - UW[k]))), int(v0 + h * (z - za) / (zb - za)))


def paint(reg, seed):
    u0, v0, w, h, za, zb = reg
    dz = (zb - za) / h
    for py in range(h):
        z = za + (zb - za) * (py + 0.5) / h
        r = ring(z)
        zone = sum(1 for pz in PANEL_Z if pz <= z)
        near = min(PANEL_Z, key=lambda pz: abs(z - pz))
        dzl = z - near
        for px in range(w):
            f = (px + 0.5) / w
            k = max(j for j in range(NSEG) if UW[j] <= f)
            fw = UW[k + 1] - UW[k]
            t = (f - UW[k]) / fw
            dt = 1 / (w * fw)
            p0, p1 = r[k], r[(k + 1) % NSEG]
            x, y = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
            c = gun(z * 1.1, k * 40 + t * 12, seed, zone * 16 + k)
            c = L.shade(c, 0.9 + 0.14 * max(0, min(1, (y - 5) / 25)))           # сверху светлее
            if y < 8:
                c = L.mix(c, (36, 34, 31), (8 - y) * 0.09)                         # грязь снизу
            if abs(x) > 4 and y > 24 and 18 < z < 46:                              # копоть от выхлопа
                c = L.mix(c, (20, 19, 18), min(0.7, math.exp(-(z - 18) / 14) * 0.8))
            # швы панелей с фаской и заклёпками
            if abs(dzl) < dz:
                c = LINE
            elif 0 < dzl < dz * 2.2:
                c = L.shade(c, 1.22)
            elif dz * 3 < abs(dzl) < dz * 4 and int(t / dt) % 7 == 0:
                c = (104, 106, 110)
            if t < dt * 1.2:
                c = L.shade(c, 0.55)
            elif t < dt * 2.4:
                c = L.shade(c, 1.18)
            elif dt * 4 < t < dt * 5 and int(z / dz) % 7 == 0:
                c = (100, 102, 106)
            if k in (2, 7) and abs(t - 0.5) < dt and -28 < z < 21:
                c = LINE                                                          # продольный шов борта
            L.put(u0 + px, v0 + py, c)


paint(REG_A, 11)
paint(REG_B, 12)


def rect_px(x0, y0, x1, y1, col, width=1):
    for i in range(width):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            L.put(x, y0 + i, col)
            L.put(x, y1 - i, col)
        for y in range(min(y0, y1), max(y0, y1) + 1):
            L.put(x0 + i, y, col)
            L.put(x1 - i, y, col)


def hatch(k, z0, z1, t0, t1):
    """Лючок на грани k: рамка с фаской и четыре винта."""
    ax, ay = to_px(k, t0, z0)
    bx, by = to_px(k, t1, z1)
    x0, x1, y0, y1 = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
    rect_px(x0, y0, x1, y1, LINE)
    rect_px(x0 + 1, y0 + 1, x1 - 1, y1 - 1, HILITE)
    for px, py in ((x0 + 3, y0 + 3), (x1 - 3, y0 + 3), (x0 + 3, y1 - 3), (x1 - 3, y1 - 3)):
        L.rivet(px, py, (120, 122, 126), (20, 20, 22))


def text_on(k, z, t, text, scale=2, col=STENCIL):
    """Трафаретная надпись на грани k, читается снаружи слева направо."""
    bx, by = to_px(k, t, z)
    right = k in (0, 1, 2, 3, 4)
    dv = -1 if right else 1      # вдоль z
    du = 1 if right else -1      # вниз по грани
    cx = 0
    for ch in text.upper():
        g = L.FONT3.get(ch, L.FONT3[" "])
        for gy in range(5):
            for gx in range(3):
                if g[gy * 3 + gx] == "1":
                    for sy in range(scale):
                        for sx in range(scale):
                            L.put(bx + du * (gy * scale + sy), by + dv * (cx + gx * scale + sx), col)
        cx += 4 * scale


for side_k in ((1, 2, 3), (8, 7, 6)):
    up, mid, low = side_k
    for z0 in (-10, 2, 26):
        hatch(mid, z0, z0 + 3.5, 0.15, 0.45)
    hatch(low, -6, -1, 0.2, 0.7)
    hatch(up, 4, 9, 0.3, 0.8)
    hatch(mid, 60, 64, 0.2, 0.8)
    text_on(mid, -6 if mid == 7 else 5, 0.62, "FUEL", 2)
    text_on(up, -22.9 if mid == 7 else -13.1, 0.5, "EXIT", 3, (200, 176, 70))
    text_on(mid, 30 if mid == 7 else 36, 0.3, "BH-01", 2)
    text_on(mid, 66 if mid == 7 else 72, 0.4, "DANGER", 2, (180, 60, 50))
    text_on(up, 48 if mid == 7 else 56, 0.35, "KEEP CLEAR", 2, (180, 60, 50))
for k in (0, 9):
    text_on(k, -24 if k == 9 else -18, 0.5, "NO STEP", 2)


def outline_cells(cells, col=(10, 10, 11), hi=(90, 93, 98), dashed=True):
    """Щель вокруг двери: рисуем только края, где соседняя клетка — не дверь."""
    for (i, k) in cells:
        u0, v0, u1, v1 = [int(round(v)) for v in hull_uv(i, k)]
        u1 -= 1
        v1 -= 1
        edges = [((i - 1, k), [(u, v0) for u in range(u0, u1 + 1)], (0, 1)),
                 ((i + 1, k), [(u, v1) for u in range(u0, u1 + 1)], (0, -1)),
                 ((i, k - 1), [(u0, v) for v in range(v0, v1 + 1)], (1, 0)),
                 ((i, k + 1), [(u1, v) for v in range(v0, v1 + 1)], (-1, 0))]
        for nb, pts, (ix, iy) in edges:
            if nb in cells:
                continue
            for (u, v) in pts:
                L.put(u, v, col)
                L.put(u + ix, v + iy, col)
                L.put(u + 2 * ix, v + 2 * iy, col)
                L.put(u + 3 * ix, v + 3 * iy, hi)
                if dashed and ((u + v) // 5) % 2 == 0:
                    L.put(u + 8 * ix, v + 8 * iy, (170, 172, 168))
                    L.put(u + 9 * ix, v + 9 * iy, (170, 172, 168))


for cells in DOOR_CELLS.values():
    outline_cells(cells)
# жёлто-чёрная разметка у ручек дверей и шарнира рампы
for k, z in ((2, -14.6), (7, -14.6)):
    for j in range(24):
        bx, by = to_px(k, 0.55, z)
        for q in range(6):
            L.put(bx + j, by + q, (200, 170, 40) if ((j + q) // 3) % 2 == 0 else (18, 18, 18))

# ---------------------------------------------------------------------------
# Декали и рамы остекления
# ---------------------------------------------------------------------------


def side_frame(side, z, y):
    x = halfwidth(z, y)
    e = 0.05
    dz = (halfwidth(z + e, y) - halfwidth(z - e, y)) / (2 * e)
    n = norm((side, 0, -dz))
    return (side * x, y, z), n


def decal(name, side, z, y, w, h, mat, offset=0.04, thick=0.2, inside=False):
    P, n = side_frame(side, z, y)
    if inside:
        P = add(P, mul(n, -(HULL_T + offset)))
        n = mul(n, -1)
        side = -side
    else:
        P = add(P, mul(n, offset))
    Xh = (0, 0, 1) if side < 0 else (0, 0, -1)
    X = norm(sub(Xh, mul(n, dot(Xh, n))))
    Z = cross(X, n)
    return ocube(name, P, X, n, Z, (-w / 2, -thick, -h / 2), (w / 2, 0, h / 2),
                 {"up": mat, "down": mat, "north": "hull", "south": "hull", "east": "hull", "west": "hull"})


decals = []
for s in (-1, 1):
    n = "L" if s < 0 else "R"
    decals.append(decal(f"number_{n}", s, -33, 12.6, 6.4, 3.2, "number"))
    decals.append(decal(f"emblem_{n}", s, 10, 13.2, 5.5, 5.5, "emblem"))
    for i, zc in enumerate((-4, 4, 16)):
        decals.append(decal(f"window_{n}{i}", s, zc, 14.2, 3.6, 2.7, "window"))
        decals.append(decal(f"window_in_{n}{i}", s, zc, 14.2, 3.6, 2.7, "window", inside=True))
    decals.append(decal(f"intake_{n}", s, 34, 13.5, 3.5, 2.5, "grille", offset=0.06))

# рамы фонаря: рёбра вдоль вершин крыши/скосов и поперечные дуги
frames = []
for idx in (1, 2, 8, 9):
    pts = [ring(z)[idx] for z in (-58, -53, -50, -47.5, -45, -42.5, -40, -37, -34)]
    for a, b in zip(pts, pts[1:]):
        frames += rod("canopy_frame", a, b, 0.2, "metal")
for zf in (-45, -34):
    r = ring(zf)
    for a, b in zip([r[7], r[8], r[9], r[0], r[1], r[2]], [r[8], r[9], r[0], r[1], r[2], r[3]]):
        frames += rod("canopy_arch", a, b, 0.22, "metal")

# ---------------------------------------------------------------------------
# Пол, переборка, интерьер
# ---------------------------------------------------------------------------
interior = []
zs_floor = [z for z in Z_RINGS if -53 <= z <= 21]
for a, b in zip(zs_floor, zs_floor[1:]):
    hw = min(halfwidth(a, 7.0), halfwidth(b, 7.0)) - HULL_T - 0.1
    if hw > 1:
        interior.append(cube("floor", [-hw, 6.2, a], [hw, 7.0, b], "interior_dark", {"up": "floor"}))


def cap(name, z, t, dest, mat="wall", hole=None, rows=14):
    w, tw, bw, yb, ybl, ybh, yt = prof(z)
    ys = [yb + 0.4 + (yt - yb - 0.8) * i / rows for i in range(rows + 1)]
    for y0, y1 in zip(ys, ys[1:]):
        hw = min(halfwidth(z, y0 + 0.01), halfwidth(z, y1 - 0.01)) - 0.3
        if hw < 0.3:
            continue
        spans = [(-hw, hw)]
        if hole and y1 > hole[2] and y0 < hole[3]:
            spans = [(-hw, hole[0]), (hole[1], hw)]
        for xa, xb in spans:
            if xb - xa > 0.2:
                dest.append(cube(name, [xa, y0, z - t / 2], [xb, y1, z + t / 2], mat))


cap("bulkhead", -29.5, 0.8, interior, "wall", hole=(-3.5, 3.5, 7, 25))

# кабина пилотов
ck = []
ck.append(cube("instrument_panel", [-7.0, 11.2, -45.9], [7.0, 15.6, -45.0], "metal", {"south": "panel"},
               origin=[0, 11.2, -45.4], rot=[-20, 0, 0]))
ck.append(cube("glareshield", [-6.6, 15.4, -46.6], [6.6, 16.1, -44.6], "leather", origin=[0, 15.7, -45.6], rot=[-8, 0, 0]))
ck.append(cube("center_console", [-2, 7, -46], [2, 12.5, -38], "metal", {"up": "panel"}))
ck.append(cube("overhead_panel", [-3.0, 25.6, -38], [3.0, 26.4, -31], "metal", {"down": "panel"}))
for s in (-1, 1):
    x = 5.2 * s
    n = "L" if s < 0 else "R"
    ck.append(cube(f"seat_base_{n}", [x - 2.2, 7, -41.5], [x + 2.2, 10, -37.5], "seatframe"))
    ck.append(cube(f"seat_cushion_{n}", [x - 2.5, 10, -42], [x + 2.5, 11.4, -37], "seat"))
    ck.append(cube(f"seat_back_{n}", [x - 2.5, 11, -37.4], [x + 2.5, 21, -36], "seat", origin=[x, 11, -36.7], rot=[10, 0, 0]))
    ck.append(cube(f"seat_head_{n}", [x - 1.6, 20.8, -36.8], [x + 1.6, 23.2, -35.6], "seat", origin=[x, 11, -36.7], rot=[10, 0, 0]))
    ck += rod(f"cyclic_{n}", (x, 7, -41.5), (x, 13, -43), 0.3, "metal")
    ck.append(cube(f"grip_{n}", [x - 0.55, 12.8, -43.7], [x + 0.55, 14.6, -42.6], "leather"))
    ck += rod(f"collective_{n}", (x + 3.2 * s, 8.5, -37.5), (x + 3.2 * s, 10.5, -42), 0.28, "metal")
    ck.append(cube(f"pedals_{n}", [x - 1.8, 7, -46.2], [x + 1.8, 8.3, -45.5], "metal", origin=[x, 7, -45.8], rot=[-30, 0, 0]))

# грузовой отсек: кресла вдоль бортов, светильники, ящики
cab = []
for s in (-1, 1):
    n = "L" if s < 0 else "R"
    xw = s * 10.4
    for i, z in enumerate((-8, -2, 4, 10, 16)):
        xs = xw - s * 2.2
        cab.append(cube(f"seat_{n}{i}", [min(xs - s * 2.2, xs + s * 2.2), 11, z - 2.2],
                        [max(xs - s * 2.2, xs + s * 2.2), 12.2, z + 2.2], "seat"))
        xb = s * 9.5
        cab.append(cube(f"seatback_{n}{i}", [min(xb, xb - s * 1.2), 12, z - 2.2], [max(xb, xb - s * 1.2), 20.5, z + 2.2], "seat"))
        cab.append(cube(f"seathead_{n}{i}", [min(s * 7.7, s * 8.9), 20.5, z - 1.4], [max(s * 7.7, s * 8.9), 22.8, z + 1.4], "seat"))
        cab += rod(f"seatleg_{n}{i}", (xs - s * 1.6, 7, z), (xs - s * 1.6, 11, z), 0.25, "seatframe")
    cab += rod(f"rail_{n}", (s * 5.0, 28.6, -28), (s * 5.0, 28.6, 20), 0.25, "steel")
    cab += rod(f"floorrail_{n}", (s * 4, 7.1, -28), (s * 4, 7.1, 21), 0.28, "steel")
for z in (-24, -14, -4, 6, 16):
    cab.append(cube("ceiling_light", [-3.5, 29.4, z - 1.5], [3.5, 29.9, z + 1.5], "metal", {"down": "light"}))
cab.append(cube("case_big", [-8, 7, 14.5], [-2, 12, 20.5], "crate"))
cab.append(cube("case_small", [-7.5, 12, 15], [-3, 15.5, 19.5], "crate", origin=[-5, 12, 17], rot=[0, 12, 0]))
cab.append(cube("case_long", [2, 7, 16], [8, 10, 20.5], "crate"))
cab.append(cube("cargo_net", [-9, 7, 20.6], [9, 16, 20.8], "interior_dark"))
cab.append(cube("fire_ext", [8.3, 7.2, -27.8], [9.8, 13, -26.3], "red"))
cab.append(cube("med_kit", [-9.6, 18, -28.5], [-8.9, 21, -26.5], "red"))

# ---------------------------------------------------------------------------
# Капот двигателей, пилон, выхлоп
# ---------------------------------------------------------------------------
eng = []
ENG_ST = [(-38.5, 1.2, 30.0), (-37, 5.0, 31.5), (-33, 8.6, 36.8), (-26, 8.8, 37.2), (8, 8.8, 37.2), (16, 7.2, 35.8), (24, 4.6, 33.2), (30, 2.0, 31.0)]
_ez = [s[0] for s in ENG_ST]
_ea, _et = pchip(_ez, [s[1] for s in ENG_ST]), pchip(_ez, [s[2] for s in ENG_ST])


def eng_ring(z):
    a, t = _ea(z), _et(z)
    b = 29.4
    return [(-a, b, z), (-a, b + (t - b) * 0.55, z), (-a * 0.68, t, z), (a * 0.68, t, z), (a, b + (t - b) * 0.55, z), (a, b, z)]


ENG_Z = [-38.5, -37, -35, -33, -30, -26, -20, -14, -8, -2, 4, 8, 12, 16, 20, 24, 27, 30]
REG_E = (192 * S, 0, 64 * S, 64 * S, -38.5, 30)


def eng_uv(i, k):
    u0, v0, w, h, za, zb = REG_E
    return [u0 + w * k / 5, v0 + h * (ENG_Z[i] - za) / (zb - za), u0 + w * (k + 1) / 5, v0 + h * (ENG_Z[i + 1] - za) / (zb - za)]


def paint_engine():
    u0, v0, w, h, za, zb = REG_E
    dz = (zb - za) / h
    for py in range(h):
        z = za + (zb - za) * (py + 0.5) / h
        for px in range(w):
            k = px * 5 // w
            t = (px * 5 / w) - k
            c = gun(z * 1.2 + 900, k * 40 + t * 10, 21, k * 5 + (0 if z < -14 else 1 if z < 8 else 2))
            if min(abs(z + 14), abs(z - 8)) < dz or t < 5 / w:
                c = LINE
            elif min(abs(z + 14), abs(z - 8)) < dz * 2.2 or t < 10 / w:
                c = L.shade(c, 1.2)
            if k in (0, 4) and -31 < z < -21 and 0.25 < t < 0.8 and int(z / dz) % 6 < 3:
                c = (12, 12, 13)                              # жалюзи
            if k == 2 and -30 < z < 4 and (abs(t - 0.2) < 1.5 / w or abs(t - 0.8) < 1.5 / w):
                c = (190, 170, 70) if int(z / dz) % 12 < 6 else (30, 30, 30)   # граница «не наступать»
            if z > 10 and k in (0, 1, 3, 4):
                c = L.mix(c, (20, 19, 18), min(0.65, (z - 10) / 26))
            L.put(u0 + px, v0 + py, c)


paint_engine()
loft("engine", [eng_ring(z) for z in ENG_Z], [(0, 29.4, z) for z in ENG_Z], 0.5, lambda i, k, c: eng_uv(i, k),
     lambda i, k, c: eng, closed=False, inner="interior_dark")
for s in (-1, 1):
    n = "L" if s < 0 else "R"
    eng.append(cube(f"engine_intake_{n}", [min(s * 8.85, s * 9.4), 31, -31], [max(s * 8.85, s * 9.4), 34.4, -23],
                                  "hull", {("east" if s > 0 else "west"): "grille"}))
    ex = []
    tube(f"exhaust_{n}", [(s * 7.5, 33.5, 12), (s * 9.5, 33.8, 16), (s * 10.5, 34.2, 20.5)], [(1.7, 1.3), (1.8, 1.4), (1.9, 1.5)],
         6, ex, "metal", "soot", t=0.4, ref=(0, 1, 0))
    eng += ex
    eng += disc(f"exhaust_soot_{n}", (s * 10.4, 34.2, 20.3), (0.25 * s, 0, 1), 1.4, 0.2, "soot")
# пилон винта (гранёный, 8 граней)


def oct_ring(cy, cz, ax, az, ch):
    return [(ax - ch, cy, cz - az), (ax, cy, cz - az + ch), (ax, cy, cz + az - ch), (ax - ch, cy, cz + az),
            (-ax + ch, cy, cz + az), (-ax, cy, cz + az - ch), (-ax, cy, cz - az + ch), (-ax + ch, cy, cz - az)]


PYL = [(36.8, 5.4, 8.0, 2.0), (38.6, 4.6, 6.8, 1.8), (40.4, 3.3, 4.6, 1.4), (41.2, 2.4, 3.2, 1.0)]
loft("pylon", [oct_ring(y, -10, a, b, c) for y, a, b, c in PYL], [(0, y, -10) for y, *_ in PYL], 0.4,
     lambda i, k, c: "hull", lambda i, k, c: eng, inner="interior_dark")
eng += disc("pylon_top", (0, 41.25, -10), (0, 1, 0), 2.6, 0.2, "metal")
_mast = []
tube("mast", [(0, 40.5, -10), (0, 43.0, -10)], [1.1, 1.0], 8, _mast, "metal", "metal", ref=(1, 0, 0))
eng += _mast
eng += disc("swashplate", (0, 41.8, -10), (0, 1, 0), 2.4, 0.6, "steel")
eng += rod("ir_jammer", (0, 37.2, 20), (0, 38.8, 20), 1.1, "metal")
eng += disc("beacon_top", (0, 37.6, 2), (0, 1, 0), 0.7, 0.6, "red")

# ---------------------------------------------------------------------------
# Спонсоны, крылья-пилоны, ракетные блоки, сенсор
# ---------------------------------------------------------------------------
side = []


def sponson(s):
    n = "L" if s < 0 else "R"
    pts, rads = [], []
    for z, k in ((-8, 0.35), (-6, 0.8), (-3, 1), (13, 1), (16, 0.8), (18, 0.35)):
        pts.append((s * 13.6, 10.5, z))
        rads.append((3.2 * k, 4.0 * k))
    out = []
    tube(f"sponson_{n}", pts, rads, 6, out, "hull", "interior_dark", t=0.45, ref=(1, 0, 0))
    return out


for s in (-1, 1):
    n = "L" if s < 0 else "R"
    side += sponson(s)
    # крыло-пилон
    wing = []
    tube(f"stub_wing_{n}", [(s * 12.5, 16.5, -2), (s * 18, 16.1, -2), (s * 23.2, 15.7, -2)],
         [(0.8, 4.2), (0.7, 3.8), (0.6, 3.2)], 6, wing, "hull", "interior_dark", t=0.3, ref=(0, 1, 0))
    side += wing
    side += disc(f"wing_light_{n}", (s * 23.4, 15.7, -2), (1, 0, 0), 0.7, 0.4, "green" if s > 0 else "red")
    # ракетный блок
    pod = []
    tube(f"rocket_pod_{n}", [(s * 20.5, 11.8, -11), (s * 20.5, 11.8, -10), (s * 20.5, 11.8, 5), (s * 20.5, 11.8, 7)],
         [2.4, 2.7, 2.7, 2.0], 8, pod, "metal", "interior_dark", t=0.35, ref=(0, 1, 0))
    side += pod
    side += disc(f"rocket_face_{n}", (s * 20.5, 11.8, -11.05), (0, 0, 1), 2.4, 0.2, "metal", "rocket")
    side += rod(f"pod_pylon_{n}", (s * 20.5, 14.4, -3), (s * 20.5, 15.8, -3), 0.8, "metal")
# сенсорная турель и фары под носом
side += disc("sensor_ball_a", (0, 6.2, -55.5), (1, 0, 0), 2.6, 3.6, "metal")
side += disc("sensor_ball_b", (0, 6.2, -55.5), (0, 0, 1), 2.6, 3.6, "metal")
side += disc("sensor_lens", (0, 6.2, -57.4), (0, 0, 1), 1.3, 0.4, "metal", "blue")
for s in (-1, 1):
    side += disc(f"nose_light_{s}", (s * 2.6, 10.4, -60.1), (0, 0.3, 1), 0.9, 0.4, "metal", "blue")
side += rod("antenna_top", (0, 30, -26), (0, 33.5, -24), 0.18, "metal")
side += rod("antenna_belly", (0, 5, 10), (0, 2.3, 12), 0.18, "metal")

# ---------------------------------------------------------------------------
# Хвост: киль с рулевым винтом, стабилизатор с шайбами, подфюзеляжный киль
# ---------------------------------------------------------------------------
tail = []
FIN_ROOT, FIN_DIR = (0, 23.2, 97.0), (0, math.cos(math.radians(28)), math.sin(math.radians(28)))
tube("tail_fin", [add(FIN_ROOT, mul(FIN_DIR, s)) for s in (0, 6, 12, 17, 20.5)],
     [(1.3, 7.2), (1.15, 6.2), (1.0, 5.2), (0.85, 4.4), (0.7, 3.8)], 6, tail, "hull", "interior_dark", t=0.3, ref=(1, 0, 0))
tail += disc("fin_cap", add(FIN_ROOT, mul(FIN_DIR, 20.6)), FIN_DIR, 0.8, 0.3, "hull")
tube("ventral_fin", [(0, 21.5, 96), (0, 17, 99)], [(0.7, 3.2), (0.5, 2.2)], 6, tail, "hull", "interior_dark", t=0.25, ref=(1, 0, 0))
tail += rod("tail_skid", (0, 17.2, 99), (0, 16.6, 101.5), 0.35, "steel")
for s in (-1, 1):
    n = "L" if s < 0 else "R"
    tube(f"stabilizer_{n}", [(s * 2.2, 22.4, 99), (s * 8, 22.4, 99.5), (s * 13.5, 22.4, 100)],
         [(0.55, 3.4), (0.5, 3.0), (0.45, 2.6)], 6, tail, "hull", "interior_dark", t=0.25, ref=(0, 1, 0))
    tube(f"endplate_{n}", [(s * 13.6, 19.5, 100.6), (s * 13.6, 22.4, 100), (s * 13.6, 27, 101.2)],
         [(0.4, 2.2), (0.45, 2.8), (0.35, 1.8)], 6, tail, "hull", "interior_dark", t=0.25, ref=(1, 0, 0))
TR = add(FIN_ROOT, mul(FIN_DIR, 16))
TR = (2.4, TR[1], TR[2])
_tg = []
tube("tail_gearbox", [(-0.6, TR[1], TR[2]), (1.2, TR[1], TR[2]), (2.0, TR[1], TR[2])], [(1.8, 2.1), (1.8, 2.1), (1.1, 1.1)],
     8, _tg, "metal", "metal", ref=(0, 1, 0))
tail += _tg
tail += disc("tail_light", add(FIN_ROOT, mul(FIN_DIR, 20.8)), (0, 0, 1), 0.4, 0.5, "red")

# ---------------------------------------------------------------------------
# Винты
# ---------------------------------------------------------------------------
HUB = (0, 43.4, -10)
rotor_children = []
rotor_children += disc("hub_low", (HUB[0], HUB[1] - 0.2, HUB[2]), (0, 1, 0), 3.4, 1.2, "metal")
rotor_children += disc("hub_high", (HUB[0], HUB[1] + 1.0, HUB[2]), (0, 1, 0), 2.6, 1.2, "metal")
rotor_children += disc("hub_cap", (HUB[0], HUB[1] + 2.0, HUB[2]), (0, 1, 0), 1.4, 0.9, "steel")
for k in range(4):
    blade = []
    blade += rod(f"blade{k}_grip", (2.6, HUB[1], HUB[2]), (9, HUB[1], HUB[2]), 0.9, "metal")
    blade += rod(f"blade{k}_link", (2.6, HUB[1] + 1.2, HUB[2] + 0.9), (7, HUB[1] + 1.0, HUB[2] + 0.9), 0.3, "steel")
    blade.append(cube(f"blade{k}", [9, HUB[1] - 0.3, HUB[2] - 2.6], [66, HUB[1] + 0.3, HUB[2] + 2.0], "bladeedge",
                      {"up": "bladestrip", "down": "bladestrip"}))
    blade.append(cube(f"blade{k}_te", [9, HUB[1] - 0.2, HUB[2] + 2.0], [66, HUB[1] + 0.1, HUB[2] + 2.6], "bladeedge"))
    blade.append(cube(f"blade{k}_tip", [66, HUB[1] - 0.3, HUB[2] - 2.6], [69, HUB[1] + 0.3, HUB[2] + 1.6], "tip",
                      origin=[66, HUB[1], HUB[2]], rot=[0, -12, 0]))
    rotor_children.append(group(f"blade_{k}", HUB, blade, rotation=[0, 45 + k * 90, 0]))
main_rotor = group("main_rotor", HUB, rotor_children)

tr_children = disc("tail_rotor_hub", (2.9, TR[1], TR[2]), (1, 0, 0), 1.3, 1.4, "metal")
tr_children += disc("tail_rotor_cap", (3.8, TR[1], TR[2]), (1, 0, 0), 0.7, 0.8, "steel")
for k in range(4):
    tr_children.append(group(f"tr_blade_{k}", TR, [
        cube(f"tr_blade{k}", [2.7, TR[1] + 1.2, TR[2] - 1.1], [3.2, TR[1] + 11, TR[2] + 1.1], "bladeedge",
             {"east": "bladestrip", "west": "bladestrip"}),
        cube(f"tr_blade{k}_tip", [2.7, TR[1] + 11, TR[2] - 1.1], [3.2, TR[1] + 12.5, TR[2] + 1.1], "tip"),
    ], rotation=[k * 90, 0, 0]))
tail_rotor = group("tail_rotor", TR, tr_children)
tail.append(tail_rotor)

# ---------------------------------------------------------------------------
# Шасси
# ---------------------------------------------------------------------------


def wheel(name, c, r, w):
    out = []
    x = c[0]
    pr = [(-w / 2, r * 0.82), (-w * 0.3, r), (w * 0.3, r), (w / 2, r * 0.82)]
    tube(name, [(x + dx, c[1], c[2]) for dx, _ in pr], [rr for _, rr in pr], 16, out, "tire", "tireside",
         t=0.5, ref=(0, 1, 0), edge="tire")
    for sg in (-1, 1):
        out += disc(f"{name}_side", (x + sg * (w / 2 - 0.1), c[1], c[2]), (1, 0, 0), r * 0.84, 0.3, "tireside")
        out += disc(f"{name}_rim", (x + sg * (w / 2 + 0.05), c[1], c[2]), (1, 0, 0), r * 0.52, 0.35, "metal")
        out += disc(f"{name}_hub", (x + sg * (w / 2 + 0.3), c[1], c[2]), (1, 0, 0), r * 0.2, 0.4, "steel")
    return out


def main_gear(s):
    n = "L" if s < 0 else "R"
    parts = wheel(f"wheel_{n}", (s * 14.2, 4.4, 9.5), 4.4, 3.0)
    parts += rod(f"gear_arm_{n}", (s * 14.2, 4.4, 9.5), (s * 14.0, 8.6, 3.5), 0.7, "metal")
    parts += rod(f"gear_shock_{n}", (s * 14.2, 5.2, 8.5), (s * 13.8, 10.5, 9.0), 0.55, "steel")
    return group(f"gear_main_{n}", (s * 14, 8.6, 3.5), parts)


nose = []
nose += rod("nose_strut", (0, 3.3, -47.5), (0, 6.2, -49), 0.5, "steel")
nose += rod("nose_axle", (-2.9, 3.3, -47.5), (2.9, 3.3, -47.5), 0.35, "metal")
nose += wheel("wheel_nose_L", (-1.9, 3.3, -47.5), 3.2, 1.8)
nose += wheel("wheel_nose_R", (1.9, 3.3, -47.5), 3.2, 1.8)

# ---------------------------------------------------------------------------
# Двери
# ---------------------------------------------------------------------------
for s, lst in ((-1, side_l), (1, side_r)):
    n = "L" if s < 0 else "R"
    lst.append(decal(f"door_window_{n}", s, -18, 14.2, 3.6, 2.7, "window", offset=0.08))
    lst.append(cube(f"door_handle_{n}", [min(s * 12.25, s * 12.9), 12.5, -14.5], [max(s * 12.25, s * 12.9), 13.2, -13.2], "steel"))
# поручни и подножки у дверей — сразу видно, где вход
for s_ in (-1, 1):
    n = "L" if s_ < 0 else "R"
    for zr in (-25.3, -10.7):
        fus.extend(rod(f"grab_rail_{n}", (s_ * 12.75, 10.2, zr), (s_ * 12.75, 15.8, zr), 0.22, "steel"))
        for yr in (10.4, 15.6):
            fus.extend(rod(f"grab_rail_mount_{n}", (s_ * 12.2, yr, zr), (s_ * 12.8, yr, zr), 0.18, "steel"))
    fus.append(cube(f"door_step_{n}", [min(s_ * 10.6, s_ * 12.6), 5.2, -22.5], [max(s_ * 10.6, s_ * 12.6), 5.7, -13.5],
                    "floor", {"up": "floor", "down": "metal"}))
    fus.append(cube(f"door_rail_top_{n}", [min(s_ * 11.0, s_ * 11.9), 26.3, -24.5], [max(s_ * 11.0, s_ * 11.9), 26.9, -2],
                    "metal", origin=[s_ * 11.45, 26.6, -13], rot=[0, 0, -s_ * 22]))
door_l = group("side_door_L", (-12.2, 7, -24), side_l)
door_r = group("side_door_R", (12.2, 7, -24), side_r)
rampg = group("rear_ramp", (0, 6.0, 21), ramp + [cube("ramp_floor", [-8, 6.3, 21.2], [8, 6.9, 30], "interior_dark", {"up": "floor"},
                                                         origin=[0, 6.0, 21], rot=[-18, 0, 0])])

# ---------------------------------------------------------------------------
# Иерархия и анимации
# ---------------------------------------------------------------------------
body = group("body", (0, 18, 0), [
    group("fuselage", (0, 18, 0), fus + decals + frames),
    group("cockpit", (0, 12, -40), ck),
    group("cabin_interior", (0, 12, 0), interior + cab),
    group("engines", (0, 33, -10), eng),
    group("sponsons_weapons", (0, 12, 0), side),
    group("tail", (0, 24, 80), tail),
    door_l, door_r, rampg,
])
gear = group("landing_gear", (0, 6, 0), [main_gear(-1), main_gear(1), group("gear_nose", (0, 6.2, -49), nose)])
root = group("helicopter", (0, 18, 0), [body, main_rotor, gear])
root["isOpen"] = body["isOpen"] = True
G = index_groups(root)

Z3 = (0, 0, 0)
FLY = 32
GD = (0, -0.6, 0)
A = lambda n, ln, lp, tr: animation(n, ln, lp, tr, G)
anims = [
    A("rotor_idle", 1.0, "loop", {"main_rotor": {"rotation": spin(1, 1.0, 1)}, "tail_rotor": {"rotation": spin(0, 1.0, 5)}}),
    A("rotor_startup", 5.0, "hold_on_last_frame", {"main_rotor": {"rotation": ramp_spin(1, 0, 5, 360)},
                                                   "tail_rotor": {"rotation": ramp_spin(0, 0, 5, 1800)}}),
    A("rotor_shutdown", 6.0, "hold_on_last_frame", {"main_rotor": {"rotation": ramp_spin(1, 0, 6, 360, speed_up=False)},
                                                    "tail_rotor": {"rotation": ramp_spin(0, 0, 6, 1800, speed_up=False)}}),
    A("hover", 2.0, "loop", {"main_rotor": {"rotation": spin(1, 2.0, 5)}, "tail_rotor": {"rotation": spin(0, 2.0, 18)},
                             "helicopter": {"position": wave([(1, 1.0, 1)], 2.0, 8, base=(0, FLY, 0)),
                                            "rotation": wave([(0, 1.0, 1), (2, 1.2, 1)], 2.0, 8, phase=1.1)},
                             "landing_gear": {"position": [(0, GD)]}}),
    A("fly_forward", 2.0, "loop", {"main_rotor": {"rotation": spin(1, 2.0, 5)}, "tail_rotor": {"rotation": spin(0, 2.0, 18)},
                                   "helicopter": {"position": wave([(1, 0.7, 1)], 2.0, 8, base=(0, FLY, 0)),
                                                  "rotation": wave([(0, 0.8, 1), (2, 1.0, 1)], 2.0, 8, phase=0.7, base=(14, 0, 0))},
                                   "landing_gear": {"position": [(0, GD)]}}),
    A("side_doors_open", 1.0, "hold_on_last_frame", {
        "side_door_L": {"position": [(0, Z3), (0.25, (1.3, 0, 0), "catmullrom"), (1.0, (1.3, 0, 13), "catmullrom")]},
        "side_door_R": {"position": [(0, Z3), (0.25, (-1.3, 0, 0), "catmullrom"), (1.0, (-1.3, 0, 13), "catmullrom")]}}),
    A("side_doors_close", 1.0, "hold_on_last_frame", {
        "side_door_L": {"position": [(0, (1.3, 0, 13)), (0.75, (1.3, 0, 0), "catmullrom"), (1.0, Z3, "catmullrom")]},
        "side_door_R": {"position": [(0, (-1.3, 0, 13)), (0.75, (-1.3, 0, 0), "catmullrom"), (1.0, Z3, "catmullrom")]}}),
    A("ramp_open", 2.0, "hold_on_last_frame", {"rear_ramp": {"rotation": [(0, Z3), (2.0, (-44, 0, 0), "catmullrom")]}}),
    A("ramp_close", 2.0, "hold_on_last_frame", {"rear_ramp": {"rotation": [(0, (-44, 0, 0)), (2.0, Z3, "catmullrom")]}}),
    A("takeoff", 5.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": [(0, Z3), (1, (0, 540, 0)), (2, (0, 1260, 0)), (3, (0, 2040, 0)), (4, (0, 2880, 0)), (5, (0, 3780, 0))]},
        "tail_rotor": {"rotation": [(0, Z3), (5, (5 * 3240, 0, 0))]},
        "helicopter": {"position": [(0, Z3), (1.5, Z3, "catmullrom"), (2.2, (0, 2, 0), "catmullrom"),
                                    (3.5, (0, 16, 0), "catmullrom"), (5, (0, FLY, 0), "catmullrom")],
                       "rotation": [(0, Z3), (1.5, Z3, "catmullrom"), (2.2, (-3, 0, 0), "catmullrom"),
                                    (3.5, (5, 0, 0), "catmullrom"), (5, Z3, "catmullrom")]},
        "landing_gear": {"position": [(0, Z3), (1.5, Z3), (2.2, GD)]}}),
    A("landing", 5.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": [(0, Z3), (1, (0, 900, 0)), (2, (0, 1800, 0)), (3, (0, 2600, 0)), (4, (0, 3240, 0)), (5, (0, 3700, 0))]},
        "tail_rotor": {"rotation": [(0, Z3), (5, (5 * 2800, 0, 0))]},
        "helicopter": {"position": [(0, (0, FLY, 0)), (1.8, (0, 12, 0), "catmullrom"), (3.2, (0, 1.5, 0), "catmullrom"),
                                    (3.8, (0, -0.4, 0), "catmullrom"), (4.2, Z3, "catmullrom"), (5, Z3)],
                       "rotation": [(0, Z3), (1.8, (-6, 0, 0), "catmullrom"), (3.2, (-2, 0, 0), "catmullrom"),
                                    (3.8, (0.8, 0, 0), "catmullrom"), (4.2, Z3, "catmullrom"), (5, Z3)]},
        "landing_gear": {"position": [(0, GD), (3.6, GD), (3.8, (0, 0.4, 0)), (4.2, Z3)]}}),
    A("crash", 4.0, "hold_on_last_frame", {
        "main_rotor": {"rotation": [(0, Z3), (1, (0, 800, 0)), (2, (0, 1450, 0)), (3, (0, 1900, 0)), (3.3, (0, 1990, 0)),
                                    (4, (0, 2010, 0), "catmullrom")]},
        "tail_rotor": {"rotation": [(0, Z3), (0.4, (500, 0, 0)), (0.6, (560, 0, 0))]},
        "helicopter": {"position": [(0, (0, FLY, 0)), (1, (2, 28, 3), "catmullrom"), (2, (6, 18, 6), "catmullrom"),
                                    (3, (8, 4, 8), "catmullrom"), (3.3, (8.5, 0, 8.5), "catmullrom"),
                                    (3.5, (8.6, 1.2, 8.6), "catmullrom"), (4, (8.8, 0, 8.8), "catmullrom")],
                       "rotation": [(0, Z3), (1, (6, 150, -4), "catmullrom"), (2, (10, 400, -8), "catmullrom"),
                                    (3, (12, 600, -12), "catmullrom"), (3.3, (8, 640, -18), "catmullrom"),
                                    (3.6, (4, 648, -16), "catmullrom"), (4, (5, 650, -17), "catmullrom")]},
        "landing_gear": {"position": [(0, GD), (3.2, GD), (3.4, (0, 1.4, 0))]},
        **{f"blade_{k}": {"rotation": [(0, Z3), (3.3, Z3), (3.5, (0, 0, -6 - 2 * k), "catmullrom"),
                                       (4, (0, 0, -8 - 2 * k), "catmullrom")]} for k in range(4)}}),
]

# --- проверка: ничего из интерьера не торчит сквозь обшивку


def inside_hull(x, y, z, m):
    if z < -61 or z > 105:
        return False
    w, tw, bw, yb, ybl, ybh, yt = prof(z)
    return yb + m < y < yt - m and abs(x) < halfwidth(z, y) - m


def all_uuids(g):
    out = []
    for c in g["children"]:
        out += [c] if isinstance(c, str) else all_uuids(c)
    return out


bad = check_inside(all_uuids(G["cockpit"]) + all_uuids(G["cabin_interior"]), inside_hull)
for name, p in bad:
    print("  ! торчит наружу:", name, p)
print("проверка интерьера:", "OK" if not bad else f"{len(bad)} элементов снаружи")

tex_png = png_bytes()
with open(os.path.join(HERE, "black_hawk_texture.png"), "wb") as f:
    f.write(tex_png)
write_bbmodel(os.path.join(HERE, "black_hawk.bbmodel"), "black_hawk", root, anims, tex_png, "black_hawk_texture.png")
print(f"elements: {len(L.elements)}, groups: {len(G)}, animations: {len(anims)}")

# ---------------------------------------------------------------------------
# Экспорт для плагина
# ---------------------------------------------------------------------------
parts = export_parts(TYPE_ID, root, G, [
    ("bh_body", None, (0, 20, 22), {}),
    ("bh_main_rotor", "main_rotor", None, {"anim": "spin", "axis": "y", "speed": 40}),
    ("bh_tail_rotor", "tail_rotor", None, {"anim": "spin", "axis": "x", "speed": 110}),
    ("bh_side_door_l", "side_door_L", None, {"anim": "slide", "door": "side_l", "out": [-1.3, 0, 0], "slide": [0, 0, 13]}),
    ("bh_side_door_r", "side_door_R", None, {"anim": "slide", "door": "side_r", "out": [1.3, 0, 0], "slide": [0, 0, 13]}),
    ("bh_rear_ramp", "rear_ramp", None, {"anim": "hinge", "door": "ramp", "axis": "x", "angle": 44}),
], tex_png)

seats = [{"name": "Пилот", "pos": [-5.2, 11.4, -39.5], "pilot": True},
         {"name": "Второй пилот", "pos": [5.2, 11.4, -39.5]}]
for s, n in ((-1, "Левый борт"), (1, "Правый борт")):
    for i, z in enumerate((-8, -2, 4, 10, 16)):
        seats.append({"name": f"{n} {i + 1}", "pos": [s * 8.2, 12.2, z]})

collision = [[-14.2, 0.3, 9.5], [14.2, 0.3, 9.5], [0, 0.3, -47.5], [0, 16.5, 101]]
for z in range(-56, 24, 8):
    collision += [[-12, 9, z], [12, 9, z], [-11.5, 17, z], [11.5, 17, z], [0, 5.5, z], [0, 30.5, z]]
collision += [[0, 12, -62], [0, 20, -55], [-20.5, 11.8, -2], [20.5, 11.8, -2], [-23, 15.7, -2], [23, 15.7, -2],
              [0, 37.5, -10], [0, 42, -10]]
collision += [[0, 23, z] for z in range(30, 106, 8)] + [[0, 40, 106], [-13.6, 24, 101], [13.6, 24, 101]]

write_type(TYPE_ID, {
    "name": "Black Hawk",
    "storage-title": "Грузовой отсек Black Hawk",
    "storage-size": 54,
    "tilt-center": [0, 2.3, 0],
    "hub": list(HUB),
    "rotor-radius": 68,
    "exit-inside": [0, 8.5, -18],
    "exit-outside": [-24, 1, -18],
    "flight": {"max-speed": 1.45, "accel": 0.042, "turn-rate": 4.0, "climb-accel": 0.034, "health": 140},
    "parts": parts,
    "doors": [
        {"id": "side_l", "name": "Левая дверь", "ticks": 20, "open-sound": "minecraft:block.iron_trapdoor.open",
         "close-sound": "minecraft:block.iron_trapdoor.close"},
        {"id": "side_r", "name": "Правая дверь", "ticks": 20, "open-sound": "minecraft:block.iron_trapdoor.open",
         "close-sound": "minecraft:block.iron_trapdoor.close"},
        {"id": "ramp", "name": "Грузовая рампа", "ticks": 40, "open-sound": "minecraft:block.piston.extend",
         "close-sound": "minecraft:block.piston.contract"},
    ],
    "seats": seats,
    "hotspots": [
        {"action": "DOOR", "door": "side_l", "pos": [-21, 7, -18], "width": 1.6, "height": 2.4},
        {"action": "DOOR", "door": "side_l", "pos": [-7, 8, -18], "width": 1.0, "height": 2.0},
        {"action": "DOOR", "door": "side_r", "pos": [21, 7, -18], "width": 1.6, "height": 2.4},
        {"action": "DOOR", "door": "side_r", "pos": [7, 8, -18], "width": 1.0, "height": 2.0},
        {"action": "DOOR", "door": "ramp", "pos": [0, 4, 46], "width": 2.6, "height": 2.2},
        {"action": "DOOR", "door": "ramp", "pos": [0, 8, 12], "width": 1.2, "height": 2.0},
        {"action": "STORAGE", "pos": [-5, 7, 17.5], "width": 1.4, "height": 1.6},
        {"action": "STORAGE", "pos": [5, 7, 18], "width": 1.4, "height": 1.2},
    ],
    "collision": collision,
    "shell": [
        {"x": [-18, 18], "z": [-54, 21], "levels": [0, 0]},
        {"x": [-18, -10], "z": [-54, -25], "levels": [1, 2]},
        {"x": [-18, -10], "z": [-25, -11], "levels": [1, 2], "door": "side_l"},
        {"x": [-18, -10], "z": [-11, 21], "levels": [1, 2]},
        {"x": [10, 18], "z": [-54, -25], "levels": [1, 2]},
        {"x": [10, 18], "z": [-25, -11], "levels": [1, 2], "door": "side_r"},
        {"x": [10, 18], "z": [-11, 21], "levels": [1, 2]},
        {"x": [-18, 18], "z": [-62, -54], "levels": [1, 2]},
        {"x": [-18, 18], "z": [21, 32], "levels": [1, 2], "door": "ramp"},
        {"x": [-18, 18], "z": [-54, 32], "levels": [3, 3]},
        {"x": [-5, 5], "z": [32, 106], "levels": [2, 3]},
    ],
})
