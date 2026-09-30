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
import sys
import uuid
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from heli_lib import *  # noqa: E402,F401,F403
import heli_lib as L  # noqa: E402

L.set_tex(1024)
S = L.S
RNG = L.RNG
RNG.seed(1986)
PLUGIN = os.path.join(HERE, "..", "..", "paper-plugin")




# ---------------------------------------------------------------------------
# Векторы
# ---------------------------------------------------------------------------








# ---------------------------------------------------------------------------
# Текстура 256x256
# ---------------------------------------------------------------------------






















OLIVE = (84, 93, 56)
OLIVE_D = (61, 68, 41)
OLIVE_B = (96, 90, 58)
RUST = (112, 66, 36)
RUST_L = (146, 88, 44)
DARKM = (54, 56, 54)
RED = (170, 34, 28)
WHITE = (214, 212, 198)
LINE = (38, 42, 26)


def camo_color(s, t, seed=0):
    """Камуфляж + износ по координатам s,t (в «мировых» единицах)."""
    n = fbm(s * 0.05, t * 0.05, seed)
    edge = abs(n - 0.53)
    c = OLIVE if n < 0.53 else OLIVE_D
    if edge < 0.012:
        c = mix(OLIVE, OLIVE_D, 0.5)                 # мягкая граница пятен
    if 0.45 < n < 0.49:
        c = OLIVE_B
    c = noisy(c, 3)
    g = fbm(s * 0.5, t * 0.5, seed + 5, 3)
    c = shade(c, 0.9 + g * 0.2)
    fade = fbm(s * 0.9, t * 0.9, seed + 7, 2)
    if fade > 0.7:
        c = mix(c, (120, 124, 96), (fade - 0.7) * 1.6)   # выгоревшая краска
    r = fbm(s * 0.18, t * 0.18, seed + 9)
    if r > 0.72:
        c = mix(c, RUST if r < 0.77 else RUST_L, min(0.8, (r - 0.72) * 7))
    return c


def glass_px(x, y):
    W = 32 * S
    band = max(0.0, 1 - abs((x + y) - W * 0.9) / (W * 0.35))
    c = mix((80, 98, 100), (180, 196, 196), band * 0.5)
    a = 60 + band * 50
    if fbm(x * 0.08, y * 0.08, 44, 3) > 0.8:
        c, a = mix(c, (110, 100, 80), 0.3), 100
    return c + (int(a),)


tile("glass", 0, 128, 32, 32, False, glass_px)
tile("clear", 240, 240, 16, 16, True, lambda x, y: (0, 0, 0, 0))


def porthole_px(x, y):
    d = math.hypot(x - 31.5, y - 31.5)
    if d > 31.5:
        return (0, 0, 0, 0)
    if d > 27:
        a = math.atan2(y - 31.5, x - 31.5)
        if abs(((a + math.pi) / (math.pi / 4)) % 1 - 0.5) < 0.12 and 28 < d < 30.5:
            return (150, 152, 140)                   # болты рамки
        return noisy((70, 78, 48), 3)
    if d > 22:
        return noisy((28, 29, 27), 2)                # резиновый уплотнитель
    c = noisy((56, 76, 84), 3)
    if -10 < (x - y) < -2:
        c = mix(c, (190, 205, 210), 0.5)
    return c + (235,)


tile("porthole", 32, 128, 16, 16, True, porthole_px)


def star_poly(cx, cy, R, r):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


_SO, _SM, _SI = star_poly(64, 66, 62, 25), star_poly(64, 66, 55, 22), star_poly(64, 66, 49, 19.5)


def star_px(x, y):
    px, py = x + 0.5, y + 0.5
    worn = fbm(x * 0.1, y * 0.1, 3, 3)
    if in_poly(px, py, _SI):
        c = noisy(RED, 8)
        return mix(c, OLIVE, 0.55) if worn > 0.72 else c
    if in_poly(px, py, _SM):
        return noisy(WHITE, 8) if worn < 0.76 else noisy(OLIVE, 4)
    if in_poly(px, py, _SO):
        return noisy(RED, 8) if worn < 0.78 else noisy(OLIVE, 4)
    return (0, 0, 0, 0)


tile("star", 48, 128, 32, 32, True, star_px)

DIG = {
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
}


def number_px(x, y):
    sc = 7
    for i, d in enumerate("32"):
        gx, gy = (x - 16 - i * 52) // sc, (y - 6) // sc
        if 0 <= gx < 5 and 0 <= gy < 7 and DIG[d][gy][gx] == "1":
            if fbm(x * 0.12, y * 0.12, 8, 3) > 0.74:
                return (0, 0, 0, 0)
            return noisy(WHITE, 6)
    return (0, 0, 0, 0)


tile("number", 80, 128, 32, 16, True, number_px)
tile("warn", 80, 144, 16, 16, True, lambda x, y: noisy((200, 44, 32), 6) if ((x + y) // 12) % 2 == 0 else noisy((222, 218, 204), 5))
tile("red", 96, 144, 16, 16, False, lambda x, y: noisy(RED, 8))


def tire_px(x, y):
    blk = ((x // 10) + (y // 14)) % 2
    edge = (y % 14) < 2 or (x % 10) < 2
    return noisy((20, 20, 19) if edge else ((34, 34, 32) if blk else (28, 28, 27)), 2)


tile("tire", 112, 128, 32, 32, False, tire_px)
tile("tireside", 144, 128, 32, 32, False, lambda x, y: noisy((36, 36, 34) if (y // 6) % 4 else (42, 42, 40), 2))
tile("metal", 176, 128, 32, 32, False, lambda x, y: shade(noisy(DARKM, 3), 0.88 + fbm(x * 0.02, y * 0.4, 5, 2) * 0.24))


def hull_tile_px(x, y):
    if x % 64 in (0, 1) or y % 64 in (0, 1):
        return LINE
    if (x % 64 == 5 or y % 64 == 5) and (x + y) % 8 == 0:
        return (128, 134, 100)
    return camo_color(x * 0.3, y * 0.3, 2)


tile("hull", 208, 128, 32, 32, False, hull_tile_px)
tile("rust", 240, 128, 16, 32, False, lambda x, y: noisy(mix(RUST, RUST_L, fbm(x * .1, y * .1, 6)), 8))


def floor_px(x, y):
    if y % 64 < 2:
        return (30, 30, 28)
    if (x % 16 in (3, 4, 5)) and (y % 16 in (3, 4, 5)):
        return noisy((92, 92, 86), 4)               # рифление
    c = noisy((62, 62, 58), 3)
    if fbm(x * 0.05, y * 0.05, 9, 3) > 0.62:
        c = mix(c, (76, 64, 46), 0.5)               # грязь
    return c


tile("floor", 0, 160, 32, 32, False, floor_px)


def wall_px(x, y):
    if x % 48 < 4:
        return noisy((78, 88, 76), 2) if x % 48 else (50, 56, 48)   # шпангоуты
    if x % 48 == 4:
        return (130, 140, 124)
    if y % 32 in (8, 24) and x % 48 in (12, 36):
        return (150, 150, 140)
    c = noisy((104, 116, 100), 3)
    s_ = fbm(x * 0.04, y * 0.04, 10, 3)
    if s_ > 0.6:
        c = mix(c, (74, 66, 50), (s_ - 0.6) * 2)
    return c


tile("wall", 32, 160, 32, 32, False, wall_px)


def canvas_px(x, y):
    # плетёные брезентовые ремни сидений
    wx, wy = x % 24, y % 24
    horiz = wy < 10
    c = (118, 80, 50) if horiz else (104, 70, 44)
    if (horiz and wx % 12 == 0) or (not horiz and wy % 12 == 0):
        c = (84, 56, 34)
    return noisy(c, 4)


tile("canvas", 64, 160, 32, 32, False, canvas_px)
tile("leather", 96, 160, 32, 32, False, lambda x, y: shade(noisy((62, 48, 38), 3), 0.85 if y % 24 < 2 else 1))
_DIALS = [(20, 22, 15), (56, 22, 15), (92, 22, 15), (20, 62, 13), (54, 62, 13), (86, 62, 13), (114, 60, 9),
          (20, 100, 11), (50, 100, 11), (80, 100, 11), (110, 100, 11)]


def panel_px(x, y):
    for cx, cy, r in _DIALS:
        d = math.hypot(x + .5 - cx, y + .5 - cy)
        if d < r - 2:
            a = math.atan2(y - cy, x - cx)
            if abs(d - (r - 4)) < 0.8 and int((a + math.pi) / (math.pi / 8)) % 2 == 0:
                return (220, 220, 200)               # шкала
            if abs((x - cx) * math.sin(0.7) - (y - cy) * math.cos(0.7)) < 0.9 and d < r - 4:
                return (240, 220, 120)               # стрелка
            return (20, 22, 20)
        if d < r:
            return (140, 142, 134)
    if y > 116 and x % 8 in (2, 3, 4) and y % 8 in (2, 3):
        return (190, 50, 40) if (x // 8) % 3 == 0 else (180, 180, 170)
    return noisy((74, 88, 84), 3)                    # серо-зелёная панель


tile("panel", 128, 160, 32, 32, True, panel_px)


def crate_px(x, y):
    if y % 32 < 2 or x < 3 or x > 124:
        return (70, 52, 30)
    c = noisy((134, 100, 62), 6)
    if fbm(x * 0.3, y * 0.02, 13, 2) > 0.6:
        c = shade(c, 0.85)                           # волокна дерева
    return c


tile("crate", 160, 160, 32, 32, True, crate_px)
L.stencil(160 * S + 22, 160 * S + 50, "OTK", (40, 30, 20), scale=4)


def ammo_px(x, y):
    if x < 4 or y < 4 or x > 123 or y > 59:
        return (50, 56, 34)
    if 24 <= y <= 28 and 16 <= x <= 111:
        return (200, 176, 66)
    return noisy((84, 92, 54), 3)


tile("ammo", 192, 160, 32, 16, True, ammo_px)
tile("soot", 192, 176, 32, 16, False, lambda x, y: noisy((30, 28, 26), 4))
tile("grille", 224, 160, 32, 32, True, lambda x, y: (16, 16, 15) if x % 6 < 2 or y % 6 < 2 else noisy((50, 52, 48), 3))
tile("chrome", 0, 192, 32, 16, False, lambda x, y: shade(noisy((160, 160, 154), 6), 0.9 + fbm(x * 0.02, y * 0.5, 14, 2) * 0.2))
tile("moss", 32, 192, 32, 32, False, lambda x, y: noisy((72, 88, 38), 8) if fbm(x * .08, y * .08, 12) > 0.45 else noisy((86, 68, 44), 6))
tile("cable", 64, 192, 32, 16, False, lambda x, y: noisy((40, 48, 38), 3) if (x + y) % 12 > 2 else (20, 20, 20))
tile("bladestrip", 96, 192, 128, 8, True, lambda x, y: (noisy((200, 44, 32), 6) if 470 < x < 490 else noisy((222, 218, 204), 5)) if x > 470
     else shade(camo_color(x * 0.15, y * 0.5, 21), 0.75 if y < 3 or y > 28 else (1.12 if y < 7 else 1)))
tile("bladeedge", 96, 200, 128, 8, False, lambda x, y: noisy((66, 70, 58), 3))
tile("intake", 224, 192, 32, 32, True, lambda x, y: (22, 22, 21) if (x // 8 + y // 8) % 2 else (44, 45, 43))
tile("exhaust", 96, 208, 32, 16, False, lambda x, y: mix(noisy((64, 60, 54), 4), RUST, 0.35 if fbm(x * .08, y * .08, 31) > 0.6 else 0))
tile("interior_dark", 0, 208, 32, 16, False, lambda x, y: noisy((42, 46, 42), 3))
tile("glass_frame", 64, 208, 32, 16, False, lambda x, y: noisy((60, 66, 44), 3))

# ---------------------------------------------------------------------------
# Кубы
# ---------------------------------------------------------------------------


























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
REG_A = (0, 0, 128 * S, 128 * S, -48.4, Z_SPLIT)
REG_B = (128 * S, 0, 64 * S, 128 * S, Z_SPLIT, 105.6)
HULL_T = 0.6
GLASS_T = 0.15

fus_panels, side_door_panels, rear_L_panels, rear_R_panels = [], [], [], []
DOOR_CELLS = {"side": set(), "rear_L": set(), "rear_R": set()}


def is_glass(i, k, c):
    x, y, z = c
    if -28.5 <= z:
        return False
    if -47.2 <= z <= -41.8 and 7.6 <= y <= 12.6 and abs(x) > 1.2:
        return True   # нижнее остекление носа
    if -47.6 <= z <= -28.5 and 15.0 <= y <= 26.6:
        if -36 < z and y > 25.0:
            return False
        return True       # рамы — тонкие стержни (см. glass_frames), чтобы пилоту было видно
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
        DOOR_CELLS["side"].add((i, k))
        return side_door_panels
    if 20 < z < Z_SPLIT and y < 18.5:
        key = "rear_L" if x < 0 else "rear_R"
        DOOR_CELLS[key].add((i, k))
        return rear_L_panels if x < 0 else rear_R_panels
    return fus_panels


def hull_outer(i, k, c):
    return "glass" if is_glass(i, k, c) else hull_uv(i, k)


def hull_inner(i, k, c):
    if is_glass(i, k, c):
        return "clear"      # изнутри стекло полностью прозрачное
    return "wall" if c[2] < 36 else "interior_dark"


rings = [[se_point(z, th) for th in THETAS] for z in Z_RINGS]
centers = [(0, (PROF(z)[1] + PROF(z)[2]) / 2, z) for z in Z_RINGS]
loft("hull", rings, centers, lambda i, k, c: GLASS_T if is_glass(i, k, c) else HULL_T, hull_outer, hull_dest,
     inner=hull_inner, edge=lambda i, k, c: "clear" if is_glass(i, k, c) else "hull")
fus_panels += disc("nose_cap", (0, 9.95, -48.5), (0, 0, 1), 0.9, 0.3, "hull")

# тонкие рамы остекления вместо широких полос обшивки
glass_frames = []
_gz = [z for z in Z_RINGS if -47.6 <= z <= -28.5]
for kk in range(0, NSEG, 4):
    for za, zb in zip(_gz, _gz[1:]):
        pa, pb = se_point(za, THETAS[kk]), se_point(zb, THETAS[kk])
        if 14.5 <= (pa[1] + pb[1]) / 2 <= 27 or (7.2 <= (pa[1] + pb[1]) / 2 <= 13 and zb <= -41.8):
            glass_frames += rod("glass_frame", pa, pb, 0.2, "glass_frame")
for zf in (-44.8, -37.0, -28.5):
    ring_pts = [se_point(zf, th) for th in THETAS]
    for kk in range(NSEG):
        pa, pb = ring_pts[kk], ring_pts[(kk + 1) % NSEG]
        if 14.5 <= (pa[1] + pb[1]) / 2 <= 27:
            glass_frames += rod("glass_arch", pa, pb, 0.22, "glass_frame")
fus_panels += glass_frames
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
STREAKS = [(RNG.uniform(-44, 100), RNG.uniform(14, 27), RNG.uniform(3, 9), RNG.choice((-1, 1))) for _ in range(30)]


def paint_region(reg, seed):
    u0, v0, w, h, za, zb = reg
    dz = (zb - za) / h
    for py in range(h):
        z = za + (zb - za) * (py + 0.5) / h
        pts = [se_point(z, theta_at((px + 0.5) / w * NSEG)) for px in range(w)]
        near = min(PANEL_Z, key=lambda pz: abs(z - pz))
        dzl = z - near
        for px in range(w):
            x, y, _ = pts[px]
            dy = max(0.02, abs(pts[min(w - 1, px + 1)][1] - pts[max(0, px - 1)][1]) / 2)
            c = camo_color(z + (0 if x < 0 else 300), y * 1.4, seed)
            if y < 9:
                c = mix(c, (84, 74, 52), min(0.55, (9 - y) * 0.12))
            if y < 6.2:
                c = mix(c, (98, 104, 86), 0.5)              # светлое брюхо
            for sz, sy, sl, sd in STREAKS:
                if (x < 0) == (sd < 0) and abs(z - sz) < max(0.25, dz * 1.5) and sy - sl < y < sy:
                    c = mix(c, RUST, 0.35 * (y - (sy - sl)) / sl + 0.08)
            # швы с фаской и заклёпки
            if abs(dzl) < dz:
                c = LINE
            elif 0 < dzl < dz * 2.2:
                c = shade(c, 1.18)
            elif dz * 3 < abs(dzl) < dz * 4 and px % 6 == 0:
                c = (140, 146, 108)
            if z < 36:
                for pyl in PANEL_Y:
                    dd = y - pyl
                    if abs(dd) < dy:
                        c = LINE
                    elif dy * 3 < abs(dd) < dy * 4 and int(z / dz) % 6 == 0:
                        c = (140, 146, 108)
            put(u0 + px, v0 + py, c)


paint_region(REG_A, 11)
paint_region(REG_B, 12)
for cells in DOOR_CELLS.values():
    L.outline_cells(cells, hull_uv, col=(30, 32, 20), hi=(120, 128, 92), dash=(200, 196, 170))


def side_px(side, z, y):
    """Пиксель развёртки для точки борта (side = -1 левый, 1 правый) на высоте y."""
    reg = REG_A if z <= Z_SPLIT else REG_B
    u0, v0, w, h, za, zb = reg
    best, bu = 1e9, 0
    for px in range(w):
        x, yy, _ = se_point(z, theta_at((px + 0.5) / w * NSEG))
        if x * side > 0 and abs(yy - y) < best:
            best, bu = abs(yy - y), px
    return u0 + bu, int(v0 + h * (z - za) / (zb - za))


def text_side(side, z, y, text, scale=3, col=(220, 216, 196)):
    u, v = side_px(side, z, y)
    L.text_px(u, v, text, col, scale, du=1 if side > 0 else -1, dv=-1 if side > 0 else 1)


text_side(-1, -23.5, 24.2, "ВХОД", 3)
for sd in (-1, 1):
    text_side(sd, 86 if sd < 0 else 93, 24.3, "ОПАСНО", 2, (200, 60, 44))
    text_side(sd, 2 if sd < 0 else 9, 8.2, "НЕ СТУПАТЬ", 2)

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
fus_misc += rod("antenna_top", (0, 28, -6), (0, 32, -4.5), 0.2, "metal")
fus_misc += rod("antenna_belly", (0, 5.2, 10), (0, 2.5, 11.5), 0.2, "metal")
fus_misc += disc("beacon_red", (0, 28.6, 18.5), (0, 1, 0), 0.9, 0.8, "red")
fus_misc += rod("wiper_L", (-2.5, 15.3, -41.3), (-5.0, 16.9, -40.6), 0.12, "metal")
fus_misc += rod("wiper_R", (2.5, 15.3, -41.3), (5.0, 16.9, -40.6), 0.12, "metal")
fus_misc += rod("mirror_arm", (-9.6, 16, -41), (-12.5, 16.6, -42), 0.2, "metal")
fus_misc.append(cube("mirror", [-13.3, 15.8, -42.6], [-12.3, 17.4, -42.3], "metal", origin=[-12.8, 16.6, -42.4], rot=[0, 20, 0]))
_winch = []
tube("hoist_winch", [(-15.4, 26.8, -24), (-15.4, 26.8, -20)], [1.2, 1.2], 8, _winch, "metal", "metal")
fus_misc += _winch

# ---------------------------------------------------------------------------
# Кабина пилотов (интерьер)
# ---------------------------------------------------------------------------
ck = []
ck.append(cube("instrument_panel", [-7.4, 10.8, -41.0], [7.4, 15.2, -40.2], "metal", {"south": "panel"},
               origin=[0, 10.8, -40.6], rot=[-18, 0, 0]))
ck.append(cube("panel_hood", [-7.4, 15.0, -41.6], [7.4, 15.7, -39.2], "leather", origin=[0, 15.3, -40.4], rot=[-8, 0, 0]))
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




# --- проверка: ничего из интерьера не торчит сквозь обшивку


def inside_hull(x, y, z, m):
    if z < -48 or z > 105:
        return False
    a, yb, yt, nt, nb = PROF(z)
    return yb + m < y < yt - m and abs(x) < halfwidth(z, y) - m


def all_uuids(g):
    out = []
    for c in g["children"]:
        out += [c] if isinstance(c, str) else all_uuids(c)
    return out


bad = check_inside(all_uuids(GROUPS["cockpit"]) + all_uuids(GROUPS["cabin_interior"]), inside_hull)
for name, p in bad:
    print("  ! торчит наружу:", name, p)
print("проверка интерьера:", "OK" if not bad else f"{len(bad)} элементов снаружи")

tex_png = png_bytes()
with open(os.path.join(HERE, "mi8_texture.png"), "wb") as f:
    f.write(tex_png)
write_bbmodel(os.path.join(HERE, "mi8_helicopter.bbmodel"), "mi8_helicopter", root, anims, tex_png, "mi8_texture.png")
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
















def export_java():
    """Экспорт через общую библиотеку: модели частей в paper-plugin/resourcepack и types/mi8.yml."""
    import sys
    sys.path.insert(0, os.path.join(HERE, ".."))
    import heli_lib as L
    L.elements = elements
    L.JAVA_ROTATION_ORDER = JAVA_ROTATION_ORDER
    parts = L.export_parts("mi8", root, GROUPS, [
        ("mi8_body", None, (0, 20, 28), {}),
        ("mi8_main_rotor", "main_rotor", None, {"anim": "spin", "axis": "y", "speed": 36}),
        ("mi8_tail_rotor", "tail_rotor", None, {"anim": "spin", "axis": "x", "speed": 100}),
        ("mi8_side_door", "side_door", None, {"anim": "slide", "door": "side", "out": [-1.4, 0, 0], "slide": [0, 0, 9.4]}),
        ("mi8_cockpit_door", "cockpit_door", None, {"anim": "hinge", "door": "cockpit", "axis": "y", "angle": 95}),
        ("mi8_rear_door_l", "rear_door_L", None, {"anim": "hinge", "door": "rear", "axis": "y", "angle": -105}),
        ("mi8_rear_door_r", "rear_door_R", None, {"anim": "hinge", "door": "rear", "axis": "y", "angle": 105}),
    ], tex_png)
    seats = [{"name": "Пилот", "pos": [-4.6, 11.2, -32.5], "pilot": True},
             {"name": "Второй пилот", "pos": [4.6, 11.2, -32.5]}]
    seats += [{"name": f"Левая скамья {i + 1}", "pos": [-8.0, 12.4, z]} for i, z in enumerate((-8, -1, 6))]
    seats += [{"name": f"Правая скамья {i + 1}", "pos": [8.0, 12.4, z]} for i, z in enumerate((-20, -12, -4, 4, 12))]
    col = [[-17.6, 0.3, 1.5], [17.6, 0.3, 1.5], [0, 0.3, -40.2], [0, 15.8, 93]]
    for z in range(-44, 21, 8):
        col += [[-11, 9, z], [11, 9, z], [-10.5, 23, z], [10.5, 23, z], [0, 5.5, z], [0, 29, z]]
    col += [[0, 11, -48], [0, 20, -44]] + [[0, 23, z] for z in range(28, 105, 8)] + [[0, 38, 108], [0, HUB_Y + 1, -13]]
    L.write_type("mi8", {
        "name": "Ми-8",
        "storage-title": "Склад Ми-8",
        "storage-size": 54,
        "tilt-center": [0, 2.2, 0],
        "hub": [0, HUB_Y, -13],
        "rotor-radius": 84,
        "exit-inside": [-5, 9, -19.5],
        "exit-outside": [-22, 1, -19.5],
        "flight": {},
        "parts": parts,
        "doors": [
            {"id": "side", "name": "Боковая дверь", "ticks": 24, "open-sound": "minecraft:block.iron_trapdoor.open",
             "close-sound": "minecraft:block.iron_trapdoor.close"},
            {"id": "rear", "name": "Задние створки", "ticks": 32, "open-sound": "minecraft:block.iron_door.open",
             "close-sound": "minecraft:block.iron_door.close"},
            {"id": "cockpit", "name": "Дверь кабины", "ticks": 16, "open-sound": "minecraft:block.wooden_door.open",
             "close-sound": "minecraft:block.wooden_door.close"},
        ],
        "seats": seats,
        "hotspots": [
            {"action": "DOOR", "door": "side", "pos": [-20, 7, -19.5], "width": 1.4, "height": 2.4},
            {"action": "DOOR", "door": "side", "pos": [-5.5, 8, -19.5], "width": 1.0, "height": 2.0},
            {"action": "DOOR", "door": "rear", "pos": [0, 4, 38], "width": 2.6, "height": 2.2},
            {"action": "DOOR", "door": "rear", "pos": [7, 8, 18], "width": 1.0, "height": 1.8},
            {"action": "DOOR", "door": "cockpit", "pos": [0, 8, -24.5], "width": 1.0, "height": 2.0},
            {"action": "STORAGE", "pos": [-3, 7, 16], "width": 1.3, "height": 1.4},
        ],
        "collision": col,
        "shell": [
            {"x": [-17, 17], "z": [-46, 21], "levels": [0, 0]},
            {"x": [-17, -8.8], "z": [-46, -25], "levels": [1, 2]},
            {"x": [-17, -8.8], "z": [-25, -14], "levels": [1, 2], "door": "side"},
            {"x": [-17, -8.8], "z": [-14, 21], "levels": [1, 2]},
            {"x": [8.8, 17], "z": [-46, 21], "levels": [1, 2]},
            {"x": [-17, 17], "z": [-54, -46], "levels": [1, 2]},
            {"x": [-17, 17], "z": [21, 30], "levels": [1, 2], "door": "rear"},
            {"x": [-17, 17], "z": [-46, 30], "levels": [3, 3]},
            {"x": [-5, 5], "z": [30, 104], "levels": [2, 3]},
        ],
    })


export_java()
