"""Furniture definitions. Units: 1 block = 16, front of every piece faces NORTH (z = small)."""
import math

import numpy as np

from furngen import Model
from textures import (PAL, Flat, Metal, Surface, Wood, add, bevel, edge_wear, fbm, gap_shadow, grime,
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


def dresser_wood(dens=4):
    """Low 4-drawer chest in warm cherry: two small drawers on top, two wide ones below,
    nickel bail pulls, brass key escutcheons, bun feet. A lace doily and a framed photo on top."""
    m = Model("furn_dresser_wood", dens)

    drawers = [
        ("drawer_top_left", (1.0, 8.5), (7.75, 10.5)),
        ("drawer_top_right", (8.25, 8.5), (15.0, 10.5)),
        ("drawer_middle", (1.0, 5.5), (15.0, 8.0)),
        ("drawer_bottom", (1.0, 2.5), (15.0, 5.0)),
    ]
    drawer_rects = [(a[0], a[1], b[0], b[1]) for _, a, b in drawers]

    # --- carcass
    side = Surface(Wood("cherry_body", grain="y", base=0.5, ring_freq=0.5),
                   [groove(1.0, dark=-0.22, light=0.12), outline(-0.1), grime(3, -0.12), edge_wear(0.12, seed=3)])
    front_frame = Surface(Wood("cherry_body", grain="x", base=0.44),
                          [gap_shadow(drawer_rects, -0.34, dist=1), outline(-0.12)])
    back = Surface(Flat("fibreboard", base=0.42, mottle=0.12, fine=0.1, scale=0.2), [outline(-0.18), grime(3, -0.1)])
    m.box("carcass", (0.5, 2, 5), (15.5, 11, 15.5), side, skip=("up", "down"),
          over={"north": front_frame, "south": back})

    # --- top board with a moulded front edge
    top_wood = Wood("cherry_body", grain="x", base=0.58, ring_freq=0.45, streak_amt=0.16)
    top_up = Surface(top_wood, [scratches(9, 0.13, seed=4), ring_stain(12.6, 12.9, 1.1, -0.14),
                                edge_wear(0.16, seed=8), outline(-0.08)])
    top_edge = Surface(top_wood, [bevel(1, hi=0.26, lo=-0.3, sides=False), edge_wear(0.18, seed=11)])
    top_under = Surface(top_wood, [add(-0.3)])
    m.box("top", (0, 11, 4.25), (16, 12, 15.75), top_edge, over={"up": top_up, "down": top_under})

    moulding = Surface(Wood("cherry_body", grain="x", base=0.5), [bevel(1, hi=0.22, lo=-0.34, sides=False)])
    m.box("top_moulding", (0.25, 10.6, 4.6), (15.75, 11, 15.6), moulding, skip=("up",),
          over={"down": Surface(Wood("cherry_body", grain="x", base=0.3))})

    # --- plinth and bun feet
    dark = Wood("cherry_dark", grain="x", base=0.5, ring_amt=0.18)
    plinth = Surface(dark, [bevel(1, hi=0.2, lo=-0.25, sides=False), grime(2, -0.1)])
    m.box("plinth", (0.25, 1, 4.75), (15.75, 2, 15.75), plinth, over={"down": Surface(dark, [add(-0.3)])})
    foot = Surface(Wood("cherry_dark", grain="y", base=0.42), [grime(1.2, -0.12)])
    for n, (fx, fz) in enumerate(((1.75, 6.25), (14.25, 6.25), (1.75, 14.25), (14.25, 14.25))):
        m.box(f"foot_{n}", (fx - 0.75, 0, fz - 0.75), (fx + 0.75, 1, fz + 0.75), foot, skip=("up", "down"))
        m.box(f"foot_{n}_r", (fx - 0.6, 0, fz - 0.6), (fx + 0.6, 1, fz + 0.6), foot, skip=("up", "down"),
              rot=("y", 45, (fx, 0.5, fz)))

    # --- drawer fronts
    dwood = Wood("cherry_front", grain="x", base=0.5, ring_freq=0.6, ring_amt=0.24)
    dfront = Surface(dwood, [bevel(1, hi=0.2, lo=-0.28), groove(0.5, dark=-0.2, light=0.12),
                             edge_wear(0.14, seed=21)])
    dedge = Surface(dwood, [add(-0.06)])
    for name, (x1, y1), (x2, y2) in drawers:
        m.box(name, (x1, y1, 4.5), (x2, y2, 5.0), dedge, skip=("south",), over={"north": dfront})

    # --- hardware
    nickel = Surface(Metal("nickel", base=0.52), [outline(-0.18)])
    nickel_bar = Surface(Metal("nickel", base=0.62, tarnish=0.18))
    rosette = Surface(Metal("nickel", base=0.4, tarnish=0.26), [outline(-0.22)])
    brass = Surface(Metal("brass", base=0.55, tarnish=0.2), [outline(-0.2), bevel(1, 0.1, -0.12)], [keyhole])
    for name, (x1, y1), (x2, y2) in drawers[2:]:
        my = (y1 + y2) / 2
        for k, cx in enumerate((4.25, 11.75)):
            for side_, px in (("a", cx - 1.1), ("b", cx + 1.1)):
                m.box(f"{name}_rosette_{k}{side_}", (px - 0.4, my - 0.4, 4.35), (px + 0.4, my + 0.4, 4.5), rosette,
                      skip=("south",))
                m.box(f"{name}_post_{k}{side_}", (px - 0.2, my - 0.2, 3.85), (px + 0.2, my + 0.2, 4.35), nickel,
                      skip=("south",))
            m.box(f"{name}_pull_{k}", (cx - 1.5, my - 0.2, 3.45), (cx + 1.5, my + 0.2, 3.85), nickel_bar)
        m.box(f"{name}_keyhole", (7.25, my - 0.875, 4.4), (8.75, my + 0.875, 4.5), brass, skip=("south",))
    for name, (x1, y1), (x2, y2) in drawers[:2]:
        cx, my = (x1 + x2) / 2, (y1 + y2) / 2
        m.box(f"{name}_knob", (cx - 0.4, my - 0.4, 3.9), (cx + 0.4, my + 0.4, 4.5), nickel, skip=("south",))
        m.box(f"{name}_knob_r", (cx - 0.4, my - 0.4, 3.95), (cx + 0.4, my + 0.4, 4.45), nickel, skip=("south",),
              rot=("z", 45, (cx, my, 4.2)))

    # --- decor on top
    m.box("doily", (1.75, 12, 6.25), (9.25, 12.08, 13.75), lace_doily(5.5, 10.0, 3.75),
          skip=("north", "south", "west", "east", "down"))
    frame_side = Surface(Wood("frame_wood", grain="y", base=0.45))
    cardboard = Surface(Flat("cardboard", base=0.5, mottle=0.2), [outline(-0.2)])
    m.box("photo_frame", (10.5, 12, 9.0), (14.0, 16.0, 9.5), frame_side, skip=("down",),
          over={"north": photo_front, "south": cardboard}, rot=("x", 22.5, (12.25, 12, 9.0)))
    return m


MODELS = {
    "furn_dresser_wood": (dresser_wood, 9201, "Деревянный комод"),
}
