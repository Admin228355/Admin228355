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


MODELS = {
    "furn_dresser_wood": (dresser_wood, 9201, "Деревянный комод"),
}
