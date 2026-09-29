"""Terrain pieces that hide the blocky landscape: slopes, corners, overhangs, rocks, grass.

1 block = 16 units, pieces are placed like the furniture (armor stand head / floor item frame, 1:1).
Slopes rise toward SOUTH (+z) / EAST (+x). Built from 45-degree rotated boxes (allowed in 1.16.5);
everything of those boxes that falls outside the block is cut away with alpha, so every piece is a
clean, closed shape and does not depend on neighbouring blocks.
"""
import math

import numpy as np

from furngen import AXIS_OF, NORMAL, Model, axis_rot
from textures import fbm, quantize, ramp, smoothstep, vnoise

GRASS = ramp((30, 36, 16), (50, 58, 26), (72, 80, 36), (96, 100, 50), (124, 124, 70), n=8)
DRY = ramp((52, 46, 24), (78, 70, 38), (104, 94, 56), (132, 120, 78), n=6)
DIRT = ramp((22, 17, 12), (38, 29, 21), (56, 44, 32), (78, 63, 46), (102, 86, 64), n=8)
STONE = ramp((30, 31, 30), (50, 51, 49), (72, 72, 69), (96, 95, 90), (126, 124, 116), n=8)
MOSS = ramp((30, 38, 20), (48, 58, 28), (68, 78, 38), n=4)

R2 = math.sqrt(2)


def world_pts(ctx):
    el = ctx.el
    if not el.rot:
        return ctx.X, ctx.Y, ctx.Z
    axis, ang, o = el.rot
    R = axis_rot(axis, ang)
    P = np.stack([ctx.X - o[0], ctx.Y - o[1], ctx.Z - o[2]], -1) @ R.T + np.array(o)
    return P[..., 0], P[..., 1], P[..., 2]


def world_normal(ctx):
    n = np.array(NORMAL[ctx.dir], float)
    if ctx.el.rot:
        n = axis_rot(ctx.el.rot[0], ctx.el.rot[1]) @ n
    return n


GRASS_LUSH = ramp((18, 26, 14), (32, 44, 20), (50, 64, 28), (70, 84, 38), (92, 104, 50), (118, 126, 66), n=10)
GRASS_DRY = ramp((34, 32, 16), (58, 54, 26), (86, 78, 40), (116, 104, 58), (146, 130, 80), (170, 154, 102), n=10)


_TILE = {}


def _periodic_field(n, freqs, rng, amp_decay=0.6):
    """Smooth field on an n x n torus (sum of integer-frequency waves -> tiles seamlessly)."""
    yy, xx = np.mgrid[0:n, 0:n] / n
    f = np.zeros((n, n))
    for k in range(1, freqs + 1):
        for _ in range(3):
            fx, fy = rng.randint(-k, k + 1, 2)
            if fx == 0 and fy == 0:
                continue
            f += amp_decay ** k * np.cos(2 * np.pi * (fx * xx + fy * yy) + rng.uniform(0, 2 * np.pi))
    f -= f.min()
    return f / max(f.max(), 1e-9)


def grass_tile(seed=11, ppu=8):
    """One block (16x16 units) of meadow, painted blade by blade, tiling seamlessly."""
    key = (seed, ppu)
    if key in _TILE:
        return _TILE[key]
    n = 16 * ppu
    rng = np.random.RandomState(seed)
    dry = _periodic_field(n, 4, rng, 0.8)
    tone = _periodic_field(n, 5, rng, 0.75)
    lush = np.array(GRASS_LUSH, float)
    dryp = np.array(GRASS_DRY, float)
    # dark, slightly earthy undergrowth
    base_i = np.clip(1.6 + 0.8 * tone, 0, 9)
    img = lush[base_i.astype(int)] * (1 - 0.5 * dry[..., None]) + dryp[np.clip(base_i.astype(int) - 1, 0, 9)] * (0.5 * dry[..., None])
    wind = rng.uniform(0, 2 * np.pi)
    count = int(n * n * 0.42)
    order = np.argsort(rng.rand(count))
    xs = rng.uniform(0, n, count)
    ys = rng.uniform(0, n, count)
    for i in order:
        x0, y0 = xs[i], ys[i]
        L = rng.uniform(0.45, 1.25) * ppu
        ang = wind + rng.normal(0, 0.35)
        d = dry[int(y0) % n, int(x0) % n]
        t = tone[int(y0) % n, int(x0) % n]
        top = np.clip(5.2 + 1.6 * t + rng.normal(0, 1.3), 2, 9)
        pal = dryp if rng.rand() < 0.18 + d * 0.3 else lush
        steps = int(L) + 1
        for k in range(steps):
            f = k / max(steps - 1, 1)
            xi = int(x0 + np.cos(ang) * k) % n
            yi = int(y0 + np.sin(ang) * k) % n
            idx = int(np.clip(top * (0.35 + 0.65 * f), 0, 9))
            img[yi, xi] = pal[idx]
    seeds = rng.rand(n, n) > 0.9985
    img[seeds] = (178, 168, 130)
    tile = img.astype(np.uint8)
    _TILE[key] = tile
    return tile


def _grass(X, Y, Z, seed):
    """Samples the blade-painted tile in world X/Z (+ a little of Y so slopes don't smear)."""
    ppu = 8
    tile = grass_tile(11, ppu)
    n = tile.shape[0]
    u = np.floor(X * ppu).astype(int) % n
    w = np.floor((Z + 0.35 * Y) * ppu).astype(int) % n
    rgb = tile[w, u]
    return np.concatenate([rgb, np.full(rgb.shape[:-1] + (1,), 255, np.uint8)], -1)


def _dirt(X, Y, Z, seed):
    g = fbm(X * 0.6, Y * 0.6, Z * 0.6, seed + 3, 3)
    f = vnoise(X * 3.1, Y * 3.1, Z * 3.1, seed + 4)
    img = quantize(np.clip(0.42 + 0.4 * (g - 0.5) + 0.3 * (f - 0.5), 0, 1), DIRT)
    peb = vnoise(X * 1.6, Y * 1.6, Z * 1.6, seed + 5) > 0.82
    img[peb] = quantize(np.clip(0.35 + 0.6 * (f[peb] - 0.3), 0, 1), STONE)
    return img


def _stone(X, Y, Z, seed, moss=True, top=False):
    g = fbm(X * 0.45, Y * 0.45, Z * 0.45, seed + 11, 4)
    f = vnoise(X * 2.7, Y * 2.7, Z * 2.7, seed + 12)
    crack = np.abs(fbm(X * 0.3, Y * 0.3, Z * 0.3, seed + 13, 2) - 0.5) < 0.025
    img = quantize(np.clip(0.45 + 0.55 * (g - 0.5) + 0.2 * (f - 0.5) - 0.3 * crack, 0, 1), STONE)
    if moss:
        mm = fbm(X * 0.4, Y * 0.4, Z * 0.4, seed + 14, 2) > (0.5 if top else 0.64)
        img[mm] = quantize(np.clip(0.2 + 0.7 * f[mm], 0, 1), MOSS)
    return img


def terrain(height=None, band=1.4, clip=True, seed=0, grass_sides=False):
    """Grass on surfaces that face up, dirt on sides with a grass rim under `height(x, z)`.
    Texels that land outside the block (0..16 cube) become transparent."""
    def paint(ctx):
        X, Y, Z = world_pts(ctx)
        n = world_normal(ctx)
        if n[1] > 0.3 or (grass_sides and n[1] > -0.3):
            img = _grass(X, Y, Z, seed)
        else:
            img = _dirt(X, Y, Z, seed)
            if height is not None:
                h = height(X, Z)
                jag = band * (0.6 + 0.8 * vnoise(X * 1.3, 0, Z * 1.3, seed + 21))
                rim = Y > h - jag
                img[rim] = _grass(X, Y, Z, seed)[rim]
                sh = (Y > h - jag - 0.6) & ~rim
                img[sh, :3] = (img[sh, :3] * 0.72).astype(np.uint8)
            if n[1] < -0.3:
                img[..., :3] = (img[..., :3] * 0.7).astype(np.uint8)
        if clip:
            e = 0.02
            out = (X < -e) | (X > 16 + e) | (Y < -e) | (Y > 16 + e) | (Z < -e) | (Z > 16 + e)
            if height is not None:  # nothing may stick out above the intended surface
                out |= Y > height(X, Z) + (0.2 if n[1] <= 0.3 else 0.05)
            img[out, 3] = 0
        return img
    return paint


def stone(seed=0, moss=True):
    def paint(ctx):
        X, Y, Z = world_pts(ctx)
        n = world_normal(ctx)
        img = _stone(X, Y, Z, seed, moss, top=n[1] > 0.5)
        if n[1] < -0.3:
            img[..., :3] = (img[..., :3] * 0.6).astype(np.uint8)
        return img
    return paint


def diamond_x(m, name, x1, x2, c, paint, **kw):
    """45-degree prism along x: its NORTH face is the ramp y = z - (c - c) from (z=0,y=0) to (z=c,y=c)."""
    s = c * R2 / 2
    return m.box(name, (x1, -s, c - s), (x2, s, c + s), paint, rot=("x", 45, ((x1 + x2) / 2, 0, c)), **kw)


def diamond_z(m, name, z1, z2, c, paint, **kw):
    """45-degree prism along z: its UP face is the ramp y = x from (x=0,y=0) to (x=c,y=c)."""
    s = c * R2 / 2
    return m.box(name, (c - s, -s, z1), (c + s, s, z2), paint, rot=("z", 45, (c, 0, (z1 + z2) / 2)), **kw)


def fit_cube(m, lo=(0, 0, 0), hi=(16, 16, 16)):
    pts = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float)
    m.corners = lambda: pts


# ---------------------------------------------------------------------- smooth 2-block slopes
# S-profile over 32 units (2 blocks) rising 16 (1 block): 22.5 deg -> 45 deg -> 22.5 deg.
# Only 0 / 22.5 / 45 degree element rotations exist in 1.16.5, this is the smoothest profile they allow.
_A = 16 / (2 - 2 * math.tan(math.radians(22.5)))          # length of each gentle part (~13.66)
_B = 32 - 2 * _A                                           # steep middle part (~4.69)
PROFILE = []                                               # (start, horizontal length, angle, start height)
_t, _y = -16.0, 0.0
for _len, _ang in ((_A, 22.5), (_B, 45.0), (_A, 22.5)):
    PROFILE.append((_t, _len, _ang, _y))
    _t += _len
    _y += _len * math.tan(math.radians(_ang))


def prof(t):
    """Height of the S-profile at horizontal position t (-16 .. 16), 0 before, 16 after."""
    t = np.asarray(t, float)
    h = np.zeros_like(t)
    for (t0, ln, ang, y0) in PROFILE:
        m = (t >= t0) & (t <= t0 + ln)
        h = np.where(m, y0 + (t - t0) * math.tan(math.radians(ang)), h)
    return np.where(t > 16, 16.0, np.where(t < -16, 0.0, h))


def smooth(height, mode, lo, hi, tol=0.18, seed=11, band=1.8):
    """mode 'surf': keep only texels lying on the height surface (grass);
    mode 'wall': vertical side, keep texels under the surface (dirt with a grass rim)."""
    def paint(ctx):
        X, Y, Z = world_pts(ctx)
        h = height(X, Z)
        if mode == "surf":
            img = _grass(X, Y, Z, seed)
            keep = np.abs(Y - h) < tol
        else:
            img = _dirt(X, Y, Z, seed)
            jag = band * (0.6 + 0.8 * vnoise(X * 1.3, 0, Z * 1.3, seed + 21))
            rim = Y > h - jag
            img[rim] = _grass(X, Y, Z, seed)[rim]
            sh = (Y > h - jag - 0.6) & ~rim
            img[sh, :3] = (img[sh, :3] * 0.72).astype(np.uint8)
            if ctx.dir == "down":
                img[..., :3] = (img[..., :3] * 0.7).astype(np.uint8)
            keep = (Y <= h + 0.05) | (ctx.dir == "down")
        e = 0.02
        keep &= (X >= lo[0] - e) & (X <= hi[0] + e) & (Z >= lo[1] - e) & (Z <= hi[1] + e) & (Y >= -e)
        img[~keep, 3] = 0
        return img
    return paint


def segs_z(m, name, x1, x2, paint):
    """Profile along +z (surface rising toward south), one element per profile part."""
    for k, (t0, ln, ang, y0) in enumerate(PROFILE):
        L = ln / math.cos(math.radians(ang))
        m.box(f"{name}_{k}", (x1, y0 - 0.5, t0), (x2, y0, t0 + L), paint,
              skip=("north", "south", "west", "east", "down"), rot=("x", -ang, ((x1 + x2) / 2, y0, t0)))


def segs_x(m, name, z1, z2, paint):
    """Profile along +x (surface rising toward east)."""
    for k, (t0, ln, ang, y0) in enumerate(PROFILE):
        L = ln / math.cos(math.radians(ang))
        m.box(f"{name}_{k}", (t0, y0 - 0.5, z1), (t0 + L, y0, z2), paint,
              skip=("north", "south", "west", "east", "down"), rot=("z", ang, (t0, y0, (z1 + z2) / 2)))


def wall(m, name, frm, to, face, paint):
    m.box(name, frm, to, paint, skip=tuple(d for d in ("north", "south", "west", "east", "up", "down") if d != face))


def fit_cube(m, lo=(0, 0, 0), hi=(16, 16, 16)):
    pts = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float)
    m.corners = lambda: pts


def slope(dens=4):
    """Smooth slope, 1 block wide, 2 blocks long. Entity goes into the block right in front of the
    1-high step (step to the SOUTH); the model runs one more block to the north."""
    m = Model("terrain_slope", dens)
    h = lambda x, z: prof(z) + 0 * x
    lo, hi = (0, -16), (16, 16)
    segs_z(m, "surface", 0, 16, smooth(h, "surf", lo, hi))
    wall(m, "side_w", (0, 0, -16), (0.01, 16, 16), "west", smooth(h, "wall", lo, hi))
    wall(m, "side_e", (15.99, 0, -16), (16, 16, 16), "east", smooth(h, "wall", lo, hi))
    wall(m, "back", (0, 0, 15.99), (16, 16, 16), "south", smooth(h, "wall", lo, hi))
    wall(m, "bottom", (0, 0, -16), (16, 0.01, 16), "down", smooth(h, "wall", lo, hi))
    fit_cube(m, (0, 0, -16), (16, 16, 16))
    return m


def slope_inner(dens=4):
    """Concave corner, 2x2 blocks: the step is to the SOUTH and to the EAST.
    Entity goes into the block touching both steps; the model covers it plus 3 blocks to the north/west."""
    m = Model("terrain_slope_inner", dens)
    h = lambda x, z: np.maximum(prof(z), prof(x))
    lo, hi = (-16, -16), (16, 16)
    segs_z(m, "surface_s", -16, 16, smooth(h, "surf", lo, hi))
    segs_x(m, "surface_e", -16, 16, smooth(h, "surf", lo, hi))
    wall(m, "side_n", (-16, 0, -16), (16, 16, -15.99), "north", smooth(h, "wall", lo, hi))
    wall(m, "side_w", (-16, 0, -16), (-15.99, 16, 16), "west", smooth(h, "wall", lo, hi))
    wall(m, "back_s", (-16, 0, 15.99), (16, 16, 16), "south", smooth(h, "wall", lo, hi))
    wall(m, "back_e", (15.99, 0, -16), (16, 16, 16), "east", smooth(h, "wall", lo, hi))
    wall(m, "bottom", (-16, 0, -16), (16, 0.01, 16), "down", smooth(h, "wall", lo, hi))
    fit_cube(m, (-16, 0, -16), (16, 16, 16))
    return m


def slope_outer(dens=4):
    """Convex corner, 2x2 blocks: the raised ground is diagonal (SOUTH-EAST of the entity block).
    Entity goes into the block touching that corner; the model covers it plus 3 blocks to the north/west."""
    m = Model("terrain_slope_outer", dens)
    h = lambda x, z: np.minimum(prof(z), prof(x))
    lo, hi = (-16, -16), (16, 16)
    segs_z(m, "surface_s", -16, 16, smooth(h, "surf", lo, hi))
    segs_x(m, "surface_e", -16, 16, smooth(h, "surf", lo, hi))
    wall(m, "side_s", (-16, 0, 15.99), (16, 16, 16), "south", smooth(h, "wall", lo, hi))
    wall(m, "side_e", (15.99, 0, -16), (16, 16, 16), "east", smooth(h, "wall", lo, hi))
    wall(m, "bottom", (-16, 0, -16), (16, 0.01, 16), "down", smooth(h, "wall", lo, hi))
    fit_cube(m, (-16, 0, -16), (16, 16, 16))
    return m


def _fringe(seed, depth=6.0):
    def paint(ctx):
        X, Y, Z = world_pts(ctx)
        img = _grass(X, Y, Z, seed)
        H = X if ctx.axis == "z" else Z
        cut = -1.0 - depth * (0.35 + 0.65 * vnoise(H * 0.9, 0, 0, seed + 31)) * (0.6 + 0.4 * vnoise(H * 3.5, 1, 0, seed + 32))
        img[Y < cut, 3] = 0
        dark = (Y < cut + 1.2) & (Y >= cut)
        img[dark, :3] = (img[dark, :3] * 0.75).astype(np.uint8)
        return img
    return paint


def grass_overhang(dens=4):
    """Placed on top of a cliff-edge block (in the air above it): a grass lip over the edge and
    grass hanging down the NORTH side of the block below."""
    m = Model("terrain_grass_overhang", dens)
    m.box("lip", (0, 0, -0.3), (16, 0.8, 3.5), terrain(None, seed=4, clip=False), skip=("down", "south"),
          over={"north": _fringe(4, 0.6), "west": _fringe(4, 0.6), "east": _fringe(4, 0.6)})
    m.box("fringe", (0, -7, -0.3), (16, 0, -0.05), _fringe(4), skip=("up", "down", "west", "east"),
          over={"south": _fringe(4)})
    fit_cube(m, (0, -7, -0.3), (16, 1, 16))
    return m


def grass_overhang_corner(dens=4):
    m = Model("terrain_grass_overhang_corner", dens)
    m.box("lip_n", (0, 0, -0.3), (16, 0.8, 3.5), terrain(None, seed=5, clip=False), skip=("down", "south", "west"),
          over={"north": _fringe(5, 0.6), "east": _fringe(5, 0.6)})
    m.box("lip_w", (-0.3, 0, 3.5), (3.5, 0.8, 16), terrain(None, seed=5, clip=False), skip=("down", "east", "north"),
          over={"west": _fringe(5, 0.6), "south": _fringe(5, 0.6)})
    m.box("fringe_n", (-0.3, -7, -0.3), (16, 0, -0.05), _fringe(5), skip=("up", "down", "west", "east"),
          over={"south": _fringe(5)})
    m.box("fringe_w", (-0.3, -7, -0.05), (-0.05, 0, 16), _fringe(6), skip=("up", "down", "north", "south"),
          over={"east": _fringe(6)})
    fit_cube(m, (-0.3, -7, -0.3), (16, 1, 16))
    return m


def cliff_rocks(dens=4):
    """Jagged rocks stuck to the NORTH side of a block (entity in the block in front of the wall)."""
    m = Model("terrain_cliff_rocks", dens)
    rng = np.random.RandomState(8)
    x = 0.0
    k = 0
    while x < 15.5:
        w = rng.uniform(3.0, 5.5)
        x2 = min(16.0, x + w)
        top = rng.uniform(9, 16)
        bot = rng.uniform(-1, 3)
        d = rng.uniform(1.2, 3.2)
        rot = ("y", float(rng.choice([-22.5, 0, 22.5])), ((x + x2) / 2, 0, 16 - d / 2))
        m.box(f"rock_{k}", (x, bot, 16 - d), (x2, top, 16), stone(20 + k), skip=("south",), rot=rot)
        if rng.rand() < 0.7:
            y2 = rng.uniform(bot + 2, top - 2)
            m.box(f"chunk_{k}", (x + 0.5, y2 - 1.5, 16 - d - 1.2), (x2 - 0.8, y2 + 1.5, 16 - d + 0.1),
                  stone(40 + k), skip=("south",), rot=("x", float(rng.choice([-22.5, 22.5])), ((x + x2) / 2, y2, 16 - d)))
        x = x2 - 0.4
        k += 1
    return m


def rocks(dens=4):
    m = Model("terrain_rocks", dens)
    specs = [((2, -1, 3), (9.5, 5.5, 9.5), ("y", 22.5, (5.75, 0, 6.25))),
             ((8.5, -1, 7.5), (14, 3.5, 13), ("y", -45, (11.25, 0, 10.25))),
             ((4, -1, 10), (8, 2.2, 14), ("y", 22.5, (6, 0, 12))),
             ((3.5, 4.5, 4.5), (8, 6.8, 8.5), ("x", 22.5, (5.75, 5.5, 6.5)))]
    for k, (a, b, r) in enumerate(specs):
        m.box(f"rock_{k}", a, b, stone(60 + k), skip=("down",), rot=r)
    return m


def grass_tuft(dens=4):
    def blades(seed):
        def paint(ctx):
            X, Y, Z = world_pts(ctx)
            H = ctx.fu
            hmax = ctx.H
            col = ctx.ii // 2
            hh = hmax * (0.2 + 0.8 * vnoise(col * 1.3, 0, 0, seed) ** 2.2)
            lean = (vnoise(col * 2.9, 5, 0, seed + 5) - 0.5) * 2
            yy = hmax - ctx.fv
            sel = (vnoise(col * 1.7, 3, 0, seed + 1) > 0.42)
            # tips taper: a blade gets 1 texel narrower in its top third
            tip = (yy > hh * 0.66) & ((ctx.ii % 2) == (lean > 0))
            sel = sel & ~tip
            img = quantize(np.clip(0.25 + 0.6 * (yy / hmax) + 0.25 * (vnoise(col * 2.1, yy * 0.3, 0, seed + 2) - 0.5), 0, 1), GRASS)
            dry = vnoise(col * 0.6, 7, 0, seed + 3) > 0.7
            img[dry] = quantize(np.clip(0.2 + 0.7 * (yy / hmax)[dry], 0, 1), DRY)
            img[..., 3] = np.where((yy < hh) & sel, 255, 0).astype(np.uint8)
            return img
        return paint
    m = Model("terrain_grass_tuft", dens)
    for k, (ang, s) in enumerate(((45, 1), (-45, 2), (22.5, 3), (-22.5, 4))):
        hgt = 11 if k < 2 else 8
        m.box(f"blades_{k}", (0.5, 0, 8), (15.5, hgt, 8), blades(90 + s), skip=("up", "down", "west", "east"),
              rot=("y", ang, (8, 0, 8)), shade=False)
    return m


def mound(dens=4):
    """Rounded grassy hummock: three octagonal tiers (box + the same box turned 45 degrees)."""
    m = Model("terrain_mound", dens)
    grassy = terrain(lambda x, z: -99 + 0 * x, band=0.1, clip=False, seed=7)  # grass all over
    for k, (r, y1, y2) in enumerate(((7.0, 0, 1.6), (5.2, 1.6, 3.0), (3.2, 3.0, 4.2))):
        a = r / 1.08
        m.box(f"tier_{k}", (8 - a, y1, 8 - a), (8 + a, y2, 8 + a), grassy, skip=("down",))
        b = a * 0.78
        m.box(f"tier_{k}_r", (8 - b, y1, 8 - b), (8 + b, y2 - 0.01, 8 + b), grassy, skip=("down",),
              rot=("y", 45, (8, 0, 8)))
    return m


MODELS = {
    "terrain_slope": (slope, 9301, "Склон 45°"),
    "terrain_slope_inner": (slope_inner, 9302, "Склон, внутренний угол"),
    "terrain_slope_outer": (slope_outer, 9303, "Склон, внешний угол"),
    "terrain_grass_overhang": (grass_overhang, 9304, "Свисающая трава на краю"),
    "terrain_grass_overhang_corner": (grass_overhang_corner, 9305, "Свисающая трава, угол"),
    "terrain_cliff_rocks": (cliff_rocks, 9306, "Каменная осыпь на стенку"),
    "terrain_rocks": (rocks, 9307, "Валуны"),
    "terrain_grass_tuft": (grass_tuft, 9308, "Куст травы"),
    "terrain_mound": (mound, 9309, "Земляной бугор"),
}


# ---------------------------------------------------------------------- 1-block 45-degree pieces (stair replacements)
def stair_slope45(dens=4):
    """Straight 45-degree slope inside one block (rises to the SOUTH)."""
    m = Model("terrain_slope45", dens)
    h = lambda x, z: np.clip(z, 0, 16)
    diamond_x(m, "ramp", 0, 16, 16, terrain(h, seed=1), skip=("up", "down", "south"))
    m.box("back", (0, 0, 15.99), (16, 16, 16), terrain(h, seed=1), skip=("up", "down", "north", "west", "east"))
    m.box("bottom", (0, 0, 0), (16, 0.01, 16), terrain(None, seed=1), skip=("up", "north", "south", "west", "east"))
    fit_cube(m)
    return m


def stair_inner45(dens=4):
    """Concave 45-degree corner inside one block (raised ground to the SOUTH and EAST)."""
    m = Model("terrain_slope45_inner", dens)
    h = lambda x, z: np.clip(np.maximum(x, z), 0, 16)
    diamond_x(m, "ramp_s", 0, 16, 16, terrain(h, seed=2), skip=("up", "down", "south"))
    diamond_z(m, "ramp_e", 0, 16, 16, terrain(h, seed=2), skip=("east", "down"))
    m.box("back_s", (0, 0, 15.99), (16, 16, 16), terrain(h, seed=2), skip=("up", "down", "north", "west", "east"))
    m.box("back_e", (15.99, 0, 0), (16, 16, 16), terrain(h, seed=2), skip=("up", "down", "north", "south", "west"))
    m.box("bottom", (0, 0, 0), (16, 0.01, 16), terrain(None, seed=2), skip=("up", "north", "south", "west", "east"))
    fit_cube(m)
    return m


def stair_outer45(dens=4):
    """Convex 45-degree corner inside one block (raised ground diagonal, SOUTH-EAST)."""
    m = Model("terrain_slope45_outer", dens)
    h = lambda x, z: np.clip(np.minimum(x, z), 0, 16)
    diamond_x(m, "ramp_s", 0, 16, 16, terrain(h, seed=3), skip=("up", "down", "south"))
    diamond_z(m, "ramp_e", 0, 16, 16, terrain(h, seed=3), skip=("east", "down"))
    m.box("back_s", (0, 0, 15.99), (16, 16, 16), terrain(h, seed=3), skip=("up", "down", "north", "west", "east"))
    m.box("back_e", (15.99, 0, 0), (16, 16, 16), terrain(h, seed=3), skip=("up", "down", "north", "south", "west"))
    m.box("bottom", (0, 0, 0), (16, 0.01, 16), terrain(None, seed=3), skip=("up", "north", "south", "west", "east"))
    fit_cube(m)
    return m
