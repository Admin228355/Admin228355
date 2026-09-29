"""Furniture definitions. Units: 1 block = 16, front of every piece faces NORTH (z = small)."""
import math

import numpy as np

from furngen import Model
from textures import (PAL, ramp, Flat, Metal, Surface, Wood, add, bevel, edge_wear, fbm, gap_shadow, grime,
                      groove, outline, quantize, ring_stain, scratches, vnoise)

# ---------------------------------------------------------------------- shared painters


def keyhole(ctx, img):
    """Keyhole in the middle of an escutcheon face: round head, narrow neck, flared foot."""
    if ctx.dir != "north":
        return img
    img = img.copy()
    c = ctx.pw // 2
    r = max(0, (ctx.ph - 5) // 2)
    pts = [(c - 1, r), (c, r),
           (c - 2, r + 1), (c - 1, r + 1), (c, r + 1), (c + 1, r + 1),
           (c - 1, r + 2), (c, r + 2),
           (c - 1, r + 3), (c, r + 3),
           (c - 2, r + 4), (c - 1, r + 4), (c, r + 4), (c + 1, r + 4)]
    for (i, j) in pts:
        if 0 <= i < ctx.pw and 0 <= j < ctx.ph:
            img[j, i, :3] = (18, 10, 5)
    # a bright rim pixel on the upper-left of the hole sells the depth
    if r > 0 and c - 1 >= 0:
        img[r - 1, c - 1, :3] = np.minimum(img[r - 1, c - 1, :3].astype(int) + 40, 255)
    return img


def lace_doily(cx, cz, radius):
    """Crocheted napkin: scalloped edge + rings of holes (alpha cut-outs, no semi-transparency)."""
    pal = np.array(PAL["lace"], np.uint8)

    def paint(ctx):
        dx, dz = ctx.X - cx, ctx.Z - cz
        r = np.hypot(dx, dz) / radius
        th = np.arctan2(dz, dx)
        edge = 1.0 + 0.075 * np.cos(12 * th)
        solid = r < edge * 0.97
        holes = np.zeros_like(solid)
        holes |= (r > 0.16) & (r < 0.3) & (np.cos(6 * th) > 0.45)            # centre rosette
        holes |= (r > 0.48) & (r < 0.62) & (np.cos(12 * th + 0.26) > 0.35)    # middle ring
        holes |= (r > 0.78) & (r < 0.86) & (np.cos(24 * th) > 0.2)           # outer lace
        shade = 0.72 + 0.18 * (1 - r) + 0.14 * (vnoise(ctx.X * 2.5, ctx.Y, ctx.Z * 2.5, 71) - 0.5)
        shade -= 0.22 * ((r > 0.9) & solid)
        idx = np.clip(np.round(shade * (len(pal) - 1)), 0, len(pal) - 1).astype(int)
        img = np.zeros((ctx.ph, ctx.pw, 4), np.uint8)
        img[..., :3] = pal[idx]
        img[..., 3] = np.where(solid & ~holes, 255, 0)
        return img
    return paint


def photo_front(ctx):
    """Framed old portrait: dark frame, cream mat, sepia photo of a person."""
    pw, ph, i, j = ctx.pw, ctx.ph, ctx.ii, ctx.jj
    frame = quantize(np.clip(0.45 + 0.25 * (fbm(ctx.X * 2, ctx.Y * 2, ctx.Z, 5, 2) - 0.5), 0, 1), PAL["frame_wood"])
    shade_f = np.zeros((ph, pw))
    shade_f += 0.35 * ((j == 0) | (i == 0)) - 0.3 * ((j == ph - 1) | (i == pw - 1))
    fr = quantize(np.clip(0.45 + shade_f + 0.2 * (vnoise(i * 0.7, j * 0.7, 0, 9) - 0.5), 0, 1), PAL["frame_wood"])
    img = fr.copy()
    mat = (i >= 2) & (j >= 2) & (i < pw - 2) & (j < ph - 2)
    img[mat] = (222, 210, 182, 255)
    photo = (i >= 3) & (j >= 3) & (i < pw - 3) & (j < ph - 3)
    u = (i - 3 + 0.5) / max(1, pw - 6)
    v = (j - 3 + 0.5) / max(1, ph - 6)
    bg = 0.78 - 0.28 * v + 0.12 * (vnoise(i * 0.9, j * 0.9, 3, 17) - 0.5)
    head = ((u - 0.5) / 0.2) ** 2 + ((v - 0.38) / 0.17) ** 2 < 1
    body = ((u - 0.5) / 0.42) ** 2 + ((v - 1.0) / 0.38) ** 2 < 1
    fig = np.where(head, 0.42, np.where(body, 0.24, bg))
    fig = fig - 0.18 * (head & (v < 0.3))  # hair
    sep = quantize(np.clip(fig, 0, 1), PAL["sepia"])
    img[photo] = sep[photo]
    img[~mat] = fr[~mat]
    del frame
    return img


# ---------------------------------------------------------------------- 1. Деревянный комод

OLD_WOOD = ramp((24, 17, 12), (46, 32, 22), (74, 52, 36), (104, 76, 54), (132, 102, 76), n=8)
OLD_FRONT = ramp((32, 18, 11), (64, 36, 21), (100, 60, 36), (132, 88, 58), (160, 122, 92), n=8)
DUSTY_TOP = ramp((44, 34, 28), (80, 62, 50), (116, 94, 80), (150, 130, 114), (178, 162, 146), n=8)
DARK_WOOD = ramp((16, 12, 9), (32, 23, 16), (52, 38, 27), (74, 56, 40), n=6)
OLD_BRASS = ramp((40, 30, 14), (86, 66, 30), (140, 112, 56), (190, 164, 96), n=6)


def dresser_wood(dens=4):
    """Low, wide two-drawer chest on a plinth (as on the DayZ server): faded dirty wood,
    dusty top, scuffed drawer fronts, one small brass pull per drawer. Nothing extra."""
    m = Model("furn_dresser_wood", dens)
    drawers = [("drawer_upper", (0.75, 4.6), (15.25, 7.3)), ("drawer_lower", (0.75, 1.8), (15.25, 4.4))]
    rects = [(a[0], a[1], b[0], b[1]) for _, a, b in drawers]

    wear = [grime(2.5, -0.2), scratches(7, 0.16, (0.8, 3.0), seed=2), edge_wear(0.22, px=1, density=0.55, seed=5)]
    side = Surface(Wood(OLD_WOOD, grain="y", base=0.46, ring_amt=0.18, var_amt=0.2),
                   [outline(-0.14)] + wear)
    front = Surface(Wood(OLD_WOOD, grain="x", base=0.4, var_amt=0.2),
                    [gap_shadow(rects, -0.4, dist=1), outline(-0.14), grime(2, -0.15)])
    back = Surface(Flat(DARK_WOOD, base=0.5, mottle=0.1, fine=0.06, scale=0.2), [outline(-0.15)])
    m.box("carcass", (0.25, 1.5, 5.5), (15.75, 8.5, 15.25), side, skip=("up", "down"),
          over={"north": front, "south": back}, share={"south": "dark"})

    top_w = Wood(DUSTY_TOP, grain="x", base=0.48, ring_amt=0.14, streak_amt=0.13, var_amt=0.2)
    top_up = Surface(top_w, [scratches(7, 0.07, (0.8, 2.5), seed=4), edge_wear(0.2, density=0.6, seed=8),
                             outline(-0.12)])
    top_edge = Surface(Wood(OLD_WOOD, grain="x", base=0.52), [bevel(1, hi=0.24, lo=-0.3, sides=False),
                                                                edge_wear(0.22, density=0.6, seed=11)])
    m.box("top", (0, 8.5, 5.0), (16, 9.25, 15.5), top_edge,
          over={"up": top_up}, share={"down": "dark"})

    plinth = Surface(Wood(DARK_WOOD, grain="x", base=0.5), [bevel(1, hi=0.18, lo=-0.2, sides=False),
                                                            grime(1.2, -0.15), scratches(4, 0.18, seed=6)])
    m.box("plinth", (0.5, 0, 5.75), (15.5, 1.5, 15.0), plinth, skip=("up", "down"))

    dwood = Wood(OLD_FRONT, grain="x", base=0.48, ring_amt=0.18, streak_amt=0.14, var_amt=0.22)
    dfront = Surface(dwood, [bevel(1, hi=0.2, lo=-0.3), scratches(6, 0.12, (0.6, 2.2), seed=21),
                             edge_wear(0.26, density=0.6, seed=22), grime(2, -0.12)])
    for name, (x1, y1), (x2, y2) in drawers:
        m.box(name, (x1, y1, 5.25), (x2, y2, 5.5), Surface(dwood, [add(-0.12)]), skip=("south",),
              over={"north": dfront})
        my = (y1 + y2) / 2
        brass = Surface(Metal(OLD_BRASS, base=0.5, tarnish=0.3), [outline(-0.2)])
        m.box(f"{name}_pull", (6.75, my - 0.2, 4.85), (9.25, my + 0.2, 5.1), brass)
        for k, px in enumerate((6.9, 8.85)):
            m.box(f"{name}_post_{k}", (px, my - 0.15, 5.1), (px + 0.25, my + 0.15, 5.25), brass, skip=("south",))
    return m


# ---------------------------------------------------------------------- shared bits for the rest
from textures import (RUST, box_joints, fill, frame_rect, lines, louvers, perforation, plank_seams, region,
                      rust, streaks, wmod, hcoord, vcoord)

OLIVE_METAL = ramp((18, 20, 12), (38, 42, 26), (60, 64, 40), (84, 88, 58), (118, 120, 88), n=8)
FRIDGE_WHITE = ramp((96, 94, 88), (150, 148, 140), (190, 188, 180), (214, 212, 204), (234, 232, 224), n=8)
LOCKER_BLUE = ramp((8, 28, 42), (14, 58, 86), (26, 90, 124), (52, 124, 156), (104, 156, 176), n=8)
NAVY = ramp((8, 11, 18), (18, 26, 40), (32, 44, 64), (54, 68, 92), (104, 116, 136), n=8)
CRATE_GREEN = ramp((22, 28, 20), (42, 50, 36), (66, 76, 58), (94, 104, 84), (132, 142, 120), n=8)
CASE_GRAY = ramp((14, 19, 24), (28, 37, 46), (46, 57, 68), (68, 81, 93), (104, 116, 126), n=8)
SMALL_GREEN = ramp((14, 26, 19), (26, 46, 34), (42, 68, 50), (64, 92, 70), (104, 132, 104), n=8)
STEEL = ramp((22, 22, 22), (48, 50, 50), (84, 86, 84), (128, 130, 126), (182, 182, 176), n=8)
DUST = ramp((60, 62, 64), (96, 98, 100), (130, 132, 132), (160, 160, 158), n=5)
YELLOW = (176, 166, 72)
STENCIL_DARK = (26, 30, 30)


def pix_overlay(fn, color, dirs=("north",)):
    """Overlay: paint texels where fn(ctx) is True."""
    def f(ctx, img):
        if ctx.dir not in dirs:
            return img
        m = fn(ctx)
        if not m.any():
            return img
        img = img.copy()
        img[m, :3] = color
        return img
    return f


def arrow_up(h, v1, v2, width=0.5, head=1.0):
    def fn(ctx):
        H, V = hcoord(ctx), vcoord(ctx)
        px = 1.0 / ctx.dens
        shaft = (np.abs(H - h) <= max(width / 2, px * 0.55)) & (V >= v1) & (V <= v2 - head)
        tip = (V > v2 - head) & (V <= v2) & (np.abs(H - h) <= (v2 - V) / head * head * 0.9 + px * 0.3)
        return shaft | tip
    return fn


def fake_text(rect, rows=3, seed=0, fill_ratio=0.62):
    """Stencil 'text': short dashes on a few rows (reads as text at this resolution)."""
    h1, v1, h2, v2 = rect

    def fn(ctx):
        H, V = hcoord(ctx), vcoord(ctx)
        px = 1.0 / ctx.dens
        m = np.zeros_like(H, bool)
        rng = np.random.RandomState(seed)
        step = (v2 - v1) / rows
        for r in range(rows):
            y = v2 - (r + 0.5) * step
            row = np.abs(V - y) < max(step * 0.28, px * 0.55)
            x = min(h1, h2)
            xe = max(h1, h2) - rng.uniform(0, (abs(h2 - h1)) * 0.35)
            while x < xe:
                w = rng.uniform(0.25, 0.8) * abs(h2 - h1) / 5
                if rng.rand() < fill_ratio:
                    m |= row & (H >= x) & (H <= min(x + w, xe))
                x += w + max(px, abs(h2 - h1) / 22)
        return m
    return fn


def painted_metal(pal, base=0.5, rust_amt=0.07, seed=0, grime_h=3.0):
    return Surface(Flat(pal, base=base, mottle=0.2, fine=0.08, scale=0.3, seed=seed),
                   [grime(grime_h, -0.18), streaks(-0.12, seed=seed), scratches(6, -0.12, (0.6, 2.5), seed=seed),
                    outline(-0.12)],
                   [rust(rust_amt * 0.7, seed=seed, edge=0.15, bottom=0.2)])


def painted_wood(pal, grain="x", base=0.5, seed=0, extra=()):
    return Surface(Wood(pal, grain=grain, base=base, ring_amt=0.14, streak_amt=0.2, var_amt=0.2, seed=seed),
                   [grime(2, -0.14), edge_wear(0.22, density=0.55, seed=seed), scratches(5, 0.14, seed=seed)]
                   + list(extra),
                   [rust(0.05, scale=0.8, seed=seed + 3, edge=0.1, palette=ramp((40, 34, 26), (74, 62, 46), (104, 90, 70), n=4))])


def steel_part(base=0.45):
    return Surface(Metal(STEEL, base=base, tarnish=0.3), [outline(-0.18)], [rust(0.12, scale=1.2, seed=9)])


# ---------------------------------------------------------------------- 2. Большой шкаф (оливковый металлический, 4 створки с перфорацией)
def wardrobe_big(dens=4):
    m = Model("furn_wardrobe_big", dens)
    x0, x1 = -3.0, 19.0
    body = painted_metal(OLIVE_METAL, 0.5, 0.06, seed=1)
    dark = Surface(Flat(OLIVE_METAL, base=0.3, mottle=0.12, fine=0.05))
    m.box("body", (x0, 0.5, 5), (x1, 31, 15.5), body, skip=("up", "down"),
          over={"north": dark, "south": dark}, share={"north": "dark", "south": "dark"})
    cap = painted_metal(OLIVE_METAL, 0.56, 0.08, seed=2)
    m.box("top_cap", (x0 - 0.25, 31, 4.75), (x1 + 0.25, 32, 15.75), cap.but([bevel(1, 0.18, -0.25, sides=False)]))
    m.box("plinth", (x0 + 0.25, 0, 5.25), (x1 - 0.25, 0.5, 15.25), dark, skip=("up", "down"), share={"north": "dark", "south": "dark", "east": "dark", "west": "dark"})
    edges = [x0 + 0.25, 2.625, 8.0, 13.375, x1 - 0.25]
    for k in range(4):
        a, b = edges[k] + 0.06, edges[k + 1] - 0.06
        perf = [(a + 0.8, 17.0, b - 0.8, 29.6), (a + 0.8, 1.9, b - 0.8, 12.4)]
        leaf = painted_metal(OLIVE_METAL, 0.52, 0.07, seed=10 + k).but(
            [perforation(perf, -0.5), frame_rect(perf, -0.12, 0.1), bevel(1, 0.14, -0.22)])
        m.box(f"door_{k}", (a, 1.0, 4.75), (b, 30.6, 5.0), leaf, skip=("south",))
    for k, hx in enumerate((3.6, 12.4)):
        m.box(f"lock_plate_{k}", (hx - 0.45, 13.3, 4.6), (hx + 0.45, 15.9, 4.75), steel_part(0.35), skip=("south",))
        m.box(f"handle_{k}", (hx - 0.2, 13.6, 4.15), (hx + 0.2, 15.6, 4.6), steel_part(0.55), skip=("south",))
        m.box(f"handle_grip_{k}", (hx - 0.2, 14.4, 3.7), (hx + 0.2, 14.8, 4.15), steel_part(0.55), skip=("south",))
    return m


# ---------------------------------------------------------------------- 3. Холодильник среднего размера
def fridge_medium(dens=4):
    m = Model("furn_fridge_medium", dens)
    enamel = Surface(Flat(FRIDGE_WHITE, base=0.62, mottle=0.18, fine=0.06, scale=0.25, seed=3),
                     [grime(3.5, -0.2), streaks(-0.1, seed=3), scratches(5, -0.1, seed=3), outline(-0.1)],
                     [rust(0.05, scale=0.9, seed=3, edge=0.2, bottom=0.35)])
    m.box("body", (1, 0.5, 3.75), (15, 23.5, 15.5), enamel, skip=("north", "down"),
          over={"up": enamel.but([add(-0.08)])})
    m.box("kick", (1.5, 0, 4.25), (14.5, 0.5, 15.0), Surface(Flat(STEEL, base=0.2)), skip=("up", "down"))
    door = enamel.but([bevel(1, 0.16, -0.25), fill([(1.1, 0.75, 14.9, 1.4)], -0.08)])
    m.box("door", (1.1, 0.75, 3.4), (14.9, 23.25, 3.75), door, skip=("south",))
    chrome = Surface(Metal(STEEL, base=0.62, tarnish=0.22), [outline(-0.15)])
    m.box("handle_bar", (12.6, 10.0, 2.6), (13.2, 17.0, 3.0), chrome)
    for k, y in enumerate((10.3, 16.2)):
        m.box(f"handle_post_{k}", (12.65, y, 3.0), (13.15, y + 0.5, 3.4), chrome, skip=("south",))
    badge = Surface(Metal(STEEL, base=0.6, tarnish=0.2), [outline(-0.2)],
                    [pix_overlay(lambda c: (c.jj == c.ph // 2) & (c.ii > 0) & (c.ii < c.pw - 1), (60, 62, 64))])
    m.box("badge", (2.4, 19.9, 3.28), (5.6, 20.6, 3.4), badge, skip=("south",))
    return m


# ---------------------------------------------------------------------- 4. Шкаф (синий металлический, 2 двери, жалюзи сверху)
def cabinet(dens=4):
    m = Model("furn_cabinet", dens)
    body = painted_metal(LOCKER_BLUE, 0.52, 0.1, seed=4)
    dark = Surface(Flat(LOCKER_BLUE, base=0.3, mottle=0.12, fine=0.05))
    m.box("body", (0.5, 0, 5.5), (15.5, 31.5, 15.5), body, skip=("down",),
          over={"north": dark, "south": dark}, share={"north": "dark4", "south": "dark4"})
    for k, (a, b) in enumerate(((0.6, 7.95), (8.05, 15.4))):
        vent = [(a + 1.3, 26.4, b - 1.3, 29.6)]
        hx = (b - 1.9, b - 0.7) if k == 0 else (a + 0.7, a + 1.9)
        grip = [(hx[0], 14.5, hx[1], 16.6)]
        leaf = painted_metal(LOCKER_BLUE, 0.55, 0.1, seed=20 + k).but(
            [louvers(vent, 6), fill(grip, -0.3), frame_rect(grip, -0.25, 0.2), bevel(1, 0.16, -0.25),
             lines(h=[b - 0.3] if k == 0 else [a + 0.3], v=[], amount=-0.1, within=(a, 0.5, b, 31.3))])
        m.box(f"door_{k}", (a, 0.5, 5.25), (b, 31.3, 5.5), leaf, skip=("south",))
        for j, y in enumerate((3.0, 27.5)):
            hxs = a - 0.12 if k == 0 else b + 0.02
            m.box(f"hinge_{k}_{j}", (hxs, y, 5.2), (hxs + 0.1, y + 1.5, 5.6), steel_part(0.35), skip=("south", "up", "down"))
    return m


# ---------------------------------------------------------------------- 5. Старый шкаф (тёмно-синий, жалюзи сверху и снизу)
def wardrobe_old(dens=4):
    m = Model("furn_wardrobe_old", dens)
    dusty = rust(0.12, scale=0.35, seed=7, palette=DUST)
    body = painted_metal(NAVY, 0.55, 0.06, seed=5).but(overlays=[dusty])
    dark = Surface(Flat(NAVY, base=0.3, mottle=0.12, fine=0.05))
    m.box("body", (-1, 0.75, 5), (17, 28, 15.5), body, skip=("down", "up"),
          over={"north": dark, "south": dark}, share={"north": "dark5", "south": "dark5"})
    m.box("top_cap", (-1.1, 28, 4.9), (17.1, 28.5, 15.6), body.but([bevel(1, 0.16, -0.22, sides=False)]))
    m.box("plinth", (-0.75, 0, 5.25), (16.75, 0.75, 15.25), Surface(Flat(NAVY, base=0.18)), skip=("up", "down"))
    for k, (a, b) in enumerate(((-0.8, 7.95), (8.05, 16.8))):
        vents = [(a + 1.6, 23.4, b - 1.6, 26.4), (a + 1.6, 2.4, b - 1.6, 5.0)]
        leaf = painted_metal(NAVY, 0.58, 0.08, seed=30 + k).but(
            [louvers(vents[:1], 5, light=0.3), louvers(vents[1:], 4, light=0.3), bevel(1, 0.16, -0.25)],
            overlays=[rust(0.16, scale=0.3, seed=40 + k, palette=DUST)])
        m.box(f"door_{k}", (a, 1.0, 4.75), (b, 27.75, 5.0), leaf, skip=("south",))
        hx = b - 0.8 if k == 0 else a + 0.5
        m.box(f"handle_{k}", (hx, 12.6, 4.3), (hx + 0.3, 15.2, 4.75), steel_part(0.3), skip=("south",))
    return m


# ---------------------------------------------------------------------- 6. Армейский деревянный ящик (длинный, зелёный)
def crate_army_wood(dens=4):
    m = Model("furn_crate_army_wood", dens)
    x0, x1, z0, z1 = -7.0, 23.0, 3.0, 13.0
    wood = painted_wood(CRATE_GREEN, "x", 0.5, seed=6,
                        extra=[plank_seams(2.4, "y", 0.25), box_joints((x0 + 0.5, x1 - 0.5), 0.55, 0.6)])
    m.box("body", (x0, 0.25, z0), (x1, 7.25, z1), wood, skip=("up",),
          over={"west": painted_wood(CRATE_GREEN, "z", 0.46, seed=7, extra=[plank_seams(2.4, "y", 0.25)]),
                "east": painted_wood(CRATE_GREEN, "z", 0.46, seed=8, extra=[plank_seams(2.4, "y", 0.25)])})
    lid = painted_wood(CRATE_GREEN, "x", 0.62, seed=9, extra=[plank_seams(3.4, "z", z0 - 0.1, -0.22, 0.06, dirs=("up",)),
                                                            bevel(1, 0.2, -0.3, sides=False)])
    m.box("lid", (x0 - 0.1, 7.25, z0 - 0.1), (x1 + 0.1, 9.25, z1 + 0.1), lid)
    for k, cx in enumerate((x0 + 1.6, x1 - 1.6)):
        m.box(f"cleat_{k}", (cx - 0.6, 9.25, z0 - 0.1), (cx + 0.6, 9.85, z1 + 0.1),
              painted_wood(CRATE_GREEN, "z", 0.6, seed=11 + k), skip=("down",))
    for k, mx in enumerate((5.7, 10.3)):
        m.box(f"handle_mount_{k}", (mx - 0.4, 9.25, 7.4), (mx + 0.4, 9.65, 8.6), steel_part(0.4), skip=("down",))
    m.box("handle", (5.5, 9.65, 7.7), (10.5, 10.05, 8.3), steel_part(0.5))
    for k, lx in enumerate((-1.9, 17.6)):
        m.box(f"latch_plate_{k}", (lx - 0.55, 4.6, z0 - 0.3), (lx + 0.55, 8.6, z0 - 0.1), steel_part(0.45), skip=("south",))
        m.box(f"latch_loop_{k}", (lx - 0.35, 5.2, z0 - 0.55), (lx + 0.35, 6.2, z0 - 0.3), steel_part(0.55), skip=("south",))
    for k, cx in enumerate((x0, x1)):
        sx = (cx - 0.05, cx + 0.8) if k == 0 else (cx - 0.8, cx + 0.05)
        for j, (za, zb) in enumerate(((z0 - 0.05, z0 + 0.8), (z1 - 0.8, z1 + 0.05))):
            m.box(f"corner_{k}{j}", (sx[0], 0, za), (sx[1], 1.0, zb), steel_part(0.35), skip=("down",))
    return m


# ---------------------------------------------------------------------- 7. Большой армейский ящик (сине-серый пластиковый кейс)
def crate_army_big(dens=4):
    m = Model("furn_crate_army_big", dens)
    x0, x1, z0, z1 = -6.0, 22.0, 1.0, 15.0
    latches = (16.4, 8.0, -0.4)
    shell = Surface(Flat(CASE_GRAY, base=0.5, mottle=0.2, fine=0.06, scale=0.3, seed=12),
                    [grime(2.5, -0.15), scratches(8, 0.12, seed=12), outline(-0.12)])
    front = shell.but(overlays=[
        pix_overlay(arrow_up(latches[0], 1.2, 4.6, 0.35, 1.0), YELLOW),
        pix_overlay(arrow_up(latches[2], 1.2, 4.6, 0.35, 1.0), YELLOW),
        pix_overlay(fake_text((x1 - 0.4, 4.2, x1 - 3.4, 6.6), 3, seed=1), YELLOW),
        pix_overlay(fake_text((x0 + 3.4, 4.2, x0 + 0.4, 6.6), 3, seed=2), YELLOW)])
    m.box("base", (x0, 0.3, z0), (x1, 7.0, z1), shell, skip=("up",), over={"north": front})
    m.box("foot", (x0 + 0.5, 0, z0 + 0.5), (x1 - 0.5, 0.3, z1 - 0.5), Surface(Flat(CASE_GRAY, base=0.15)), skip=("up", "down"))
    lid = shell.but([bevel(1, 0.2, -0.28, sides=False)])
    m.box("lid", (x0, 7.0, z0), (x1, 9.8, z1), lid, skip=("down",))
    for k, rx in enumerate((-3.6, 1.6, 8.0, 14.4, 19.6)):
        m.box(f"lid_rib_{k}", (rx - 0.6, 9.8, z0 + 0.4), (rx + 0.6, 10.4, z1 - 0.4), shell.but([add(0.06)]), skip=("down",))
    for k, c in enumerate(latches):
        for j, rx in enumerate((c - 2.1, c + 1.5)):
            m.box(f"rib_{k}{j}", (rx, 0.3, z0 - 0.3), (rx + 0.6, 7.0, z0), shell.but([add(0.04)]), skip=("south",))
        m.box(f"latch_base_{k}", (c - 0.8, 5.4, z0 - 0.25), (c + 0.8, 8.8, z0), Surface(Flat(CASE_GRAY, base=0.12)), skip=("south",))
        m.box(f"latch_{k}", (c - 0.5, 5.8, z0 - 0.45), (c + 0.5, 8.4, z0 - 0.25), steel_part(0.55), skip=("south",))
    for k, (sx, ex) in enumerate(((x0 - 0.4, x0), (x1, x1 + 0.4))):
        m.box(f"side_handle_{k}", (sx, 4.8, 5.5), (ex, 5.4, 10.5), Surface(Flat(CASE_GRAY, base=0.2)), skip=("west",) if k == 1 else ("east",))
    return m


# ---------------------------------------------------------------------- 8. Маленький армейский деревянный ящик
def crate_army_small(dens=4):
    m = Model("furn_crate_army_small", dens)
    x0, x1, z0, z1 = 0.0, 16.0, 3.0, 13.0
    grips = [(5.4, 2.4, 6.2, 5.0), (9.8, 2.4, 10.6, 5.0)]
    wood = painted_wood(SMALL_GREEN, "x", 0.5, seed=13, extra=[plank_seams(2.6, "y", 0.75)])
    front = wood.but([fill(grips, -0.35), frame_rect(grips, -0.2, 0.2)],
                     [pix_overlay(fake_text((6.7, 2.5, 9.3, 5.2), 4, seed=5), STENCIL_DARK)])
    m.box("body", (x0, 0.75, z0), (x1, 6.0, z1), wood, skip=("up",), over={"north": front})
    lid = painted_wood(SMALL_GREEN, "x", 0.6, seed=14, extra=[bevel(1, 0.2, -0.3, sides=False)])
    m.box("lid", (x0 - 0.1, 6.0, z0 - 0.1), (x1 + 0.1, 7.2, z1 + 0.1), lid)
    for k, cx in enumerate((x0 + 1.0, x1 - 1.0)):
        m.box(f"cleat_{k}", (cx - 0.6, 7.2, z0 - 0.1), (cx + 0.6, 7.7, z1 + 0.1),
              painted_wood(SMALL_GREEN, "z", 0.58, seed=15 + k), skip=("down",))
        m.box(f"hasp_{k}", (cx - 0.4, 4.9, z0 - 0.35), (cx + 0.4, 7.5, z0 - 0.1), steel_part(0.5), skip=("south",))
    for k, bx in enumerate((4.0, 12.0)):
        for j, (za, zb) in enumerate(((z0 - 0.3, z0), (z1, z1 + 0.3))):
            m.box(f"batten_{k}{j}", (bx - 0.5, 0, za), (bx + 0.5, 5.6, zb), painted_wood(SMALL_GREEN, "y", 0.44, seed=17 + k),
                  skip=("south",) if j == 0 else ("north",))
    rivets = lambda c: (c.jj % 3 == 1) & (c.ii == c.pw // 2)
    strap = Surface(Metal(STEEL, base=0.35, tarnish=0.3), [outline(-0.15)],
                    [rust(0.18, scale=1.2, seed=19), pix_overlay(rivets, (150, 150, 144), ("north", "south", "east", "west"))])
    for k, (a, b) in enumerate(((x0 - 0.15, x0 + 0.7), (x1 - 0.7, x1 + 0.15))):
        for j, (za, zb) in enumerate(((z0 - 0.15, z0 + 0.7), (z1 - 0.7, z1 + 0.15))):
            m.box(f"corner_{k}{j}", (a, 0.75, za), (b, 6.0, zb), strap, skip=("up", "down"))
    return m


MODELS = {
    "furn_dresser_wood": (dresser_wood, 9201, "Деревянный комод"),
    "furn_wardrobe_big": (wardrobe_big, 9202, "Большой шкаф"),
    "furn_fridge_medium": (fridge_medium, 9203, "Холодильник среднего размера"),
    "furn_wardrobe_old": (wardrobe_old, 9204, "Старый шкаф"),
    "furn_cabinet": (cabinet, 9205, "Шкаф"),
    "furn_crate_army_wood": (crate_army_wood, 9206, "Армейский деревянный ящик"),
    "furn_crate_army_big": (crate_army_big, 9207, "Большой армейский ящик"),
    "furn_crate_army_small": (crate_army_small, 9208, "Маленький армейский деревянный ящик"),
}
