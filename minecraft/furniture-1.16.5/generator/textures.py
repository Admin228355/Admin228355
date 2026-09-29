"""Procedural pixel textures: noise, palettes, materials and per-face modifiers.

A painter is any callable ctx -> uint8 RGBA array (ph, pw, 4).
`Surface(material, mods, overlays)` is the usual painter:
    material.shade(ctx) -> float map 0..1
    mods modify the shade map (bevels, grooves, grime, scratches ...)
    the map is quantised to the material palette (crisp pixel-art look)
    overlays draw straight RGBA on top (keyholes, stencils, labels ...)
"""
import math

import numpy as np

# ---------------------------------------------------------------------- noise
_M = np.uint64(0xFFFFFFFF)


def _hash3(ix, iy, iz, seed):
    h = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263
         + iz.astype(np.int64) * 1440662683 + int(seed) * 2654435761)
    h = h.astype(np.uint64) & _M
    h = ((h ^ (h >> np.uint64(13))) * np.uint64(1274126177)) & _M
    h = h ^ (h >> np.uint64(16))
    return (h & np.uint64(0xFFFF)).astype(np.float64) / 65535.0


def vnoise(x, y, z, seed=0):
    x, y, z = (np.asarray(v, float) for v in (x, y, z))
    xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
    xf, yf, zf = x - xi, y - yi, z - zi
    u, v, w = (t * t * (3 - 2 * t) for t in (xf, yf, zf))
    xi, yi, zi = xi.astype(np.int64), yi.astype(np.int64), zi.astype(np.int64)
    acc = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                wgt = (u if dx else 1 - u) * (v if dy else 1 - v) * (w if dz else 1 - w)
                acc = acc + wgt * _hash3(xi + dx, yi + dy, zi + dz, seed)
    return acc


def fbm(x, y, z, seed=0, octaves=4, lac=2.0, gain=0.5):
    amp, tot, norm = 1.0, 0.0, 0.0
    for o in range(octaves):
        tot = tot + amp * vnoise(x, y, z, seed + o * 1013)
        norm += amp
        amp *= gain
        x, y, z = x * lac, y * lac, z * lac
    return tot / norm


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------- palettes
def ramp(*stops, n=8):
    """Linear palette through the given RGB stops (dark -> light)."""
    stops = np.array(stops, float)
    t = np.linspace(0, 1, n) * (len(stops) - 1)
    i = np.minimum(t.astype(int), len(stops) - 2)
    f = (t - i)[:, None]
    return [tuple(int(round(c)) for c in row) for row in stops[i] * (1 - f) + stops[i + 1] * f]


PAL = {
    # warm cherry / mahogany varnish
    "cherry_body": ramp((40, 18, 12), (78, 36, 22), (118, 58, 34), (156, 86, 52), n=8),
    "cherry_front": ramp((58, 27, 15), (104, 50, 27), (150, 80, 44), (196, 124, 74), n=8),
    "cherry_dark": ramp((26, 12, 8), (52, 25, 15), (82, 41, 25), (110, 58, 36), n=7),
    "fibreboard": ramp((70, 50, 34), (104, 78, 55), (132, 103, 76), n=6),
    "nickel": ramp((34, 34, 36), (78, 78, 80), (140, 140, 138), (206, 206, 198), (238, 238, 230), n=8),
    "brass": ramp((52, 34, 12), (112, 80, 30), (176, 136, 58), (226, 196, 118), n=7),
    "lace": ramp((170, 160, 138), (214, 206, 186), (240, 235, 220), (252, 250, 243), n=6),
    "frame_wood": ramp((24, 14, 8), (58, 34, 18), (96, 62, 32), (140, 98, 52), n=6),
    "cardboard": ramp((92, 74, 52), (128, 106, 78), (156, 134, 102), n=5),
    "sepia": ramp((44, 30, 20), (98, 72, 48), (164, 136, 98), (218, 198, 160), n=8),
}


def quantize(shade, palette):
    n = len(palette)
    idx = np.clip(np.round(shade * (n - 1)), 0, n - 1).astype(int)
    pal = np.array(palette, np.uint8)
    rgb = pal[idx]
    a = np.full(shade.shape + (1,), 255, np.uint8)
    return np.concatenate([rgb, a], axis=-1)


# ---------------------------------------------------------------------- materials
class Wood:
    """3D wood field: a (slightly tilted) log axis along `grain`; every face of the
    element cuts the same field, so end grain shows rings and long faces show
    stripes / cathedral arches, continuous around the corners."""

    def __init__(self, palette, grain="x", base=0.5, ring_freq=0.55, ring_amt=0.22, streak_amt=0.2,
                 var_amt=0.14, warp=1.2, center_dist=(9, 22), tilt=0.12, seed=0, knot=None):
        self.palette = PAL[palette] if isinstance(palette, str) else palette
        self.grain, self.base, self.ring_freq = grain, base, ring_freq
        self.ring_amt, self.streak_amt, self.var_amt = ring_amt, streak_amt, var_amt
        self.warp, self.center_dist, self.tilt, self.seed, self.knot = warp, center_dist, tilt, seed, knot

    def shade(self, ctx):
        rng = np.random.RandomState((ctx.seed * 31 + self.seed) % (2 ** 31))
        g = self.grain
        a_ax, b_ax = [a for a in "xyz" if a != g]
        G, A, B = ctx.coord(g), ctx.coord(a_ax), ctx.coord(b_ax)
        el = ctx.el
        mid = {k: (el.frm[i] + el.to[i]) / 2 for i, k in enumerate("xyz")}
        ang = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(*self.center_dist)
        a0 = mid[a_ax] + math.cos(ang) * dist
        b0 = mid[b_ax] + math.sin(ang) * dist
        ta, tb = rng.uniform(-self.tilt, self.tilt, 2)
        s = int(rng.randint(0, 10000))
        warp = self.warp * (fbm(G * 0.06, A * 0.25, B * 0.25, s, 3) - 0.5)
        r = np.sqrt((A - (a0 + ta * G)) ** 2 + (B - (b0 + tb * G)) ** 2) + warp
        ring = (r * self.ring_freq) % 1.0
        late = smoothstep(0.62, 0.97, ring)
        streak = fbm(G * 0.12, A * 2.2, B * 2.2, s + 7, 3) - 0.5
        var = fbm(G * 0.05, A * 0.12, B * 0.12, s + 13, 2) - 0.5
        shade = (self.base + self.ring_amt * (0.35 - late) + 0.08 * ring
                 + self.streak_amt * streak + self.var_amt * var)
        return shade


class Flat:
    """Painted / plain surface with low-frequency mottling and fine grain."""

    def __init__(self, palette, base=0.5, mottle=0.18, fine=0.12, scale=0.35, seed=0):
        self.palette = PAL[palette] if isinstance(palette, str) else palette
        self.base, self.mottle, self.fine, self.scale, self.seed = base, mottle, fine, scale, seed

    def shade(self, ctx):
        s = ctx.seed + self.seed
        m = fbm(ctx.X * self.scale, ctx.Y * self.scale, ctx.Z * self.scale, s, 3) - 0.5
        f = vnoise(ctx.X * 3.1, ctx.Y * 3.1, ctx.Z * 3.1, s + 5) - 0.5
        return self.base + self.mottle * m + self.fine * f


class Metal:
    """Polished / tarnished metal: brighter on top faces, soft streaks and tarnish."""

    def __init__(self, palette, base=0.55, up=0.18, down=-0.25, tarnish=0.22, seed=0):
        self.palette = PAL[palette] if isinstance(palette, str) else palette
        self.base, self.up, self.down, self.tarnish, self.seed = base, up, down, tarnish, seed

    def shade(self, ctx):
        s = ctx.seed + self.seed
        t = fbm(ctx.X * 1.3, ctx.Y * 1.3, ctx.Z * 1.3, s, 3) - 0.5
        v = self.base + self.tarnish * t
        if ctx.dir == "up":
            v = v + self.up
        elif ctx.dir == "down":
            v = v + self.down
        # a highlight streak along the top part of vertical faces
        if ctx.dir not in ("up", "down"):
            v = v + 0.16 * (ctx.jj == 0) - 0.12 * (ctx.jj == ctx.ph - 1)
        return v


# ---------------------------------------------------------------------- modifiers
def bevel(px=1, hi=0.16, lo=-0.2, sides=True):
    def f(ctx, s):
        s = s.copy()
        for k in range(px):
            s[k, :] += hi / (k + 1)
            s[ctx.ph - 1 - k, :] += lo / (k + 1)
            if sides:
                s[:, k] += hi * 0.5 / (k + 1)
                s[:, ctx.pw - 1 - k] += lo * 0.6 / (k + 1)
        return s
    return f


def outline(amount=-0.12, px=1):
    def f(ctx, s):
        s = s.copy()
        m = (ctx.ii < px) | (ctx.jj < px) | (ctx.ii >= ctx.pw - px) | (ctx.jj >= ctx.ph - px)
        s[m] += amount
        return s
    return f


def groove(inset, dark=-0.28, light=0.14, width=1):
    """Routed line at `inset` units from the face border (looks like a recessed panel)."""
    def f(ctx, s):
        s = s.copy()
        k = int(round(inset * ctx.dens))
        pw, ph = ctx.pw, ctx.ph
        i, j = ctx.ii, ctx.jj
        inside = (i >= k) & (i < pw - k) & (j >= k) & (j < ph - k)
        for w in range(width):
            top = inside & (j == k + w)
            left = inside & (i == k + w)
            bot = inside & (j == ph - 1 - k - w)
            right = inside & (i == pw - 1 - k - w)
            s[top | left] += dark
            s[bot | right] += light
        return s
    return f


def grime(height=3.0, amount=-0.18, axis_up="y"):
    """Darker near the floor (vertical faces)."""
    def f(ctx, s):
        if ctx.dir in ("up", "down"):
            return s
        return s + amount * (1 - smoothstep(0, height, ctx.Y))
    return f


def gap_shadow(rects, amount=-0.3, dist=1):
    """Darkens texels just outside the given rectangles (x1, y1, x2, y2 in world units on the face plane)."""
    def f(ctx, s):
        s = s.copy()
        px = 1.0 / ctx.dens
        U = ctx.X if ctx.axis == "z" else ctx.Z
        V = ctx.Y
        for (u1, v1, u2, v2) in rects:
            du = np.maximum(np.maximum(u1 - U, U - u2), 0)
            dv = np.maximum(np.maximum(v1 - V, V - v2), 0)
            dd = np.maximum(du, dv)
            ring = (dd > 0) & (dd <= dist * px + 1e-6)
            below = (V < v1)  # the rail under a drawer sits in its shadow
            s[ring] += amount * np.where(below[ring], 1.0, 0.6)
        return s
    return f


def scratches(n=6, amount=0.14, length=(1.0, 3.5), seed=0):
    def f(ctx, s):
        s = s.copy()
        rng = np.random.RandomState((ctx.seed * 97 + seed) % (2 ** 31))
        for _ in range(n):
            x0, y0 = rng.uniform(0, ctx.W), rng.uniform(0, ctx.H)
            ang = rng.uniform(-0.5, 0.5) + (0 if rng.rand() < 0.7 else math.pi / 2)
            ln = rng.uniform(*length)
            x1, y1 = x0 + math.cos(ang) * ln, y0 + math.sin(ang) * ln
            px, py = ctx.fu - x0, ctx.fv - y0
            dx, dy = x1 - x0, y1 - y0
            t = np.clip((px * dx + py * dy) / (dx * dx + dy * dy), 0, 1)
            dist = np.hypot(px - t * dx, py - t * dy)
            s[dist < 0.5 / ctx.dens] += amount
        return s
    return f


def ring_stain(cx, cz, r, amount=-0.16, width=0.35):
    """Water ring left by a glass on a top face (world x/z)."""
    def f(ctx, s):
        if ctx.dir != "up":
            return s
        d = np.hypot(ctx.X - cx, ctx.Z - cz)
        return s + amount * (np.abs(d - r) < width) + amount * 0.35 * (d < r)
    return f


def edge_wear(amount=0.16, px=1, density=0.45, seed=0):
    """Rubbed-through varnish along the face border (lighter, patchy)."""
    def f(ctx, s):
        s = s.copy()
        m = (ctx.ii < px) | (ctx.jj < px) | (ctx.ii >= ctx.pw - px) | (ctx.jj >= ctx.ph - px)
        n = vnoise(ctx.X * 1.7, ctx.Y * 1.7, ctx.Z * 1.7, ctx.seed + seed)
        s[m & (n > 1 - density)] += amount
        return s
    return f


def add(amount):
    return lambda ctx, s: s + amount


class Surface:
    def __init__(self, material, mods=(), overlays=()):
        self.material, self.mods, self.overlays = material, list(mods), list(overlays)

    def __call__(self, ctx):
        s = self.material.shade(ctx)
        for m in self.mods:
            s = m(ctx, s)
        img = quantize(np.clip(s, 0, 1), self.material.palette)
        for o in self.overlays:
            img = o(ctx, img)
        return img

    def but(self, mods=(), overlays=(), material=None):
        """Copy with extra modifiers / overlays."""
        return Surface(material or self.material, self.mods + list(mods), self.overlays + list(overlays))


def solid(rgb, alpha=255):
    def f(ctx):
        img = np.zeros((ctx.ph, ctx.pw, 4), np.uint8)
        img[..., :3] = rgb
        img[..., 3] = alpha
        return img
    return f


# ---------------------------------------------------------------------- world-space helpers for decals
def hcoord(ctx):
    """Horizontal world coordinate across a face (x on north/south/up/down, z on east/west)."""
    return ctx.Z if ctx.axis == "x" else ctx.X


def vcoord(ctx):
    return ctx.Z if ctx.axis == "y" else ctx.Y


def region(ctx, h1, v1, h2, v2):
    H, V = hcoord(ctx), vcoord(ctx)
    return (H >= min(h1, h2)) & (H <= max(h1, h2)) & (V >= min(v1, v2)) & (V <= max(v1, v2))


def wmod(fn, dirs=("north",)):
    """Only apply modifier fn on the given face directions."""
    def f(ctx, s):
        return fn(ctx, s) if ctx.dir in dirs else s
    return f


def perforation(rects, amount=-0.55, pitch=2, dirs=("north",)):
    """Grid of punched holes (every `pitch` texels) inside world-space rects (h1, v1, h2, v2)."""
    def f(ctx, s):
        if ctx.dir not in dirs:
            return s
        s = s.copy()
        hole = (ctx.ii % pitch == 0) & (ctx.jj % pitch == 0)
        for r in rects:
            m = region(ctx, *r)
            s[m & hole] += amount
            s[m & ~hole] += 0.04
        return s
    return f


def louvers(rects, n, dark=-0.5, light=0.22, dirs=("north",)):
    """n horizontal vent slots in each rect: dark slit with a lit lip under it."""
    def f(ctx, s):
        if ctx.dir not in dirs:
            return s
        s = s.copy()
        V = vcoord(ctx)
        px = 1.0 / ctx.dens
        for (h1, v1, h2, v2) in rects:
            m = region(ctx, h1, v1, h2, v2)
            nn = max(1, min(n, int((v2 - v1) * ctx.dens / 2)))  # keep >= 1 lit texel between slits
            step = (v2 - v1) / nn
            for k in range(nn):
                y = v2 - (k + 0.5) * step
                s[m & (np.abs(V - y) < px * 0.55)] += dark
                s[m & (np.abs(V - (y - px)) < px * 0.55)] += light
        return s
    return f


def lines(h=(), v=(), amount=-0.35, lit=0.0, dirs=("north",), within=None):
    """1-texel seams at world positions: h = horizontal-coordinate positions (vertical lines),
    v = vertical positions (horizontal lines). `lit` brightens the texel next to it."""
    def f(ctx, s):
        if ctx.dir not in dirs:
            return s
        s = s.copy()
        H, V = hcoord(ctx), vcoord(ctx)
        px = 1.0 / ctx.dens
        lim = region(ctx, *within) if within else np.ones_like(s, bool)
        for x in h:
            s[lim & (np.abs(H - x) < px * 0.55)] += amount
            if lit:
                s[lim & (np.abs(H - (x + px)) < px * 0.55)] += lit
        for y in v:
            s[lim & (np.abs(V - y) < px * 0.55)] += amount
            if lit:
                s[lim & (np.abs(V - (y - px)) < px * 0.55)] += lit
        return s
    return f


def frame_rect(rects, dark=-0.3, light=0.14, dirs=("north",)):
    """Pressed/recessed rectangle outline (dark top-left, light bottom-right)."""
    def f(ctx, s):
        if ctx.dir not in dirs:
            return s
        s = s.copy()
        H, V = hcoord(ctx), vcoord(ctx)
        px = 1.0 / ctx.dens
        for (h1, v1, h2, v2) in rects:
            inside = region(ctx, h1, v1, h2, v2)
            top = inside & (np.abs(V - v2) < px * 0.55)
            bot = inside & (np.abs(V - v1) < px * 0.55)
            l1 = inside & (np.abs(H - h1) < px * 0.55)
            l2 = inside & (np.abs(H - h2) < px * 0.55)
            s[top | l1 | l2] += dark
            s[bot] += light
        return s
    return f


def fill(rects, amount, dirs=("north",)):
    def f(ctx, s):
        if ctx.dir not in dirs:
            return s
        s = s.copy()
        for r in rects:
            s[region(ctx, *r)] += amount
        return s
    return f


def plank_seams(period, axis="y", offset=0.0, amount=-0.3, lit=0.1, dirs=("north", "south", "west", "east")):
    """Board joints every `period` units along a world axis."""
    def f(ctx, s):
        if ctx.dir not in dirs:
            return s
        s = s.copy()
        c = ctx.coord(axis)
        px = 1.0 / ctx.dens
        ph = (c - offset) % period
        s[ph < px * 0.999] += amount
        s[(ph >= px) & (ph < 2 * px * 0.999)] += lit
        return s
    return f


def box_joints(ends, width, period, amount=-0.14, dirs=("north", "south", "west", "east")):
    """Finger-joint look at crate corners: alternating darker bands near the given world ends."""
    def f(ctx, s):
        if ctx.dir not in dirs:
            return s
        s = s.copy()
        H = hcoord(ctx)
        band = ((ctx.Y // period) % 2) == 0
        for e in ends:
            m = np.abs(H - e) < width
            s[m & band] += amount
            s[m & ~band] -= amount * 0.3
        return s
    return f


RUST = ramp((46, 22, 10), (92, 44, 18), (132, 70, 30), (164, 104, 56), n=6)


def rust(amount=0.1, scale=0.55, seed=0, edge=0.0, bottom=0.0, palette=None):
    """Overlay: rust / chipped paint blotches (world-space noise), more on edges and near the floor."""
    pal = np.array(palette or RUST, np.uint8)

    def f(ctx, img):
        n = fbm(ctx.X * scale, ctx.Y * scale, ctx.Z * scale, ctx.seed + seed + 311, 3)
        fine = vnoise(ctx.X * 2.3, ctx.Y * 2.3, ctx.Z * 2.3, ctx.seed + seed + 17)
        score = n + 0.35 * (fine - 0.5)
        if edge:
            m = (ctx.ii == 0) | (ctx.jj == 0) | (ctx.ii == ctx.pw - 1) | (ctx.jj == ctx.ph - 1)
            score = score + edge * m
        if bottom and ctx.dir not in ("up", "down"):
            score = score + bottom * (1 - smoothstep(0, 3, ctx.Y))
        m = score > (1.0 - amount)
        if not m.any():
            return img
        img = img.copy()
        idx = np.clip(((score - (1 - amount)) / max(amount, 1e-3) * 2 + fine) * (len(pal) - 1) / 2, 0, len(pal) - 1)
        img[m, :3] = pal[idx.astype(int)][m]
        return img
    return f


def streaks(amount=-0.1, scale=0.6, seed=0):
    """Vertical dirt run-downs on vertical faces."""
    def f(ctx, s):
        if ctx.dir in ("up", "down"):
            return s
        H = hcoord(ctx)
        n = fbm(H * scale * 3, ctx.Y * 0.08, 0, ctx.seed + seed + 5, 2)
        return s + amount * smoothstep(0.55, 0.8, n)
    return f
