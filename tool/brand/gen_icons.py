"""Иконки TogetherForever: два переплетённых сердца.

Перерисовывает все иконки лаунчера (основную, адаптивную и цветные для
выбора иконки в приложении) и логотипы в assets. Цвета берутся из
lib/services/app_icon_service.dart, чтобы превью в приложении совпадали
с иконкой на рабочем столе.

    pip install pillow && python3 tool/brand/gen_icons.py
"""
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / 'android/app/src/main/res'
DENS = {'mdpi': 1, 'hdpi': 1.5, 'xhdpi': 2, 'xxhdpi': 3, 'xxxhdpi': 4}
S = 1024  # рисуем крупно, потом уменьшаем


def hexc(v):
    v = v[-6:]
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def heart(cx, cy, size, angle_deg):
    a = math.radians(angle_deg)
    pts = []
    for i in range(360):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        x, y = x * size / 34, (y + 2) * size / 34
        xr = x * math.cos(a) - y * math.sin(a)
        yr = x * math.sin(a) + y * math.cos(a)
        pts.append((cx + xr, cy + yr))
    return pts


def art(fg, scale=1.0, halo=None):
    """Прозрачный слой с сердцами, [scale] — доля холста.

    Левое сердце залито, правое — кольцо поверх него: «двое, но одно целое».
    [halo] — цвет фона: тонкий зазор, отделяющий кольцо от заливки.
    """
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    size = S * 0.56 * scale
    off = S * 0.12 * scale
    c = S / 2
    lx, rx, y = c - off, c + off, c + S * 0.02 * scale

    def mask(cx, sz, ang):
        m = Image.new('L', (S, S), 0)
        ImageDraw.Draw(m).polygon(heart(cx, y, sz, ang), fill=255)
        return m

    img.paste(Image.new('RGBA', (S, S), fg + (255,)), (0, 0), mask(lx, size, -14))
    ring_w = 0.2
    outer = mask(rx, size, 14)
    inner = mask(rx, size * (1 - ring_w), 14)
    if halo is not None:
        gap = mask(rx, size * 1.1, 14)
        hole = mask(rx, size * (1 - ring_w) * 0.9, 14)
        from PIL import ImageChops
        img.paste(Image.new('RGBA', (S, S), halo + (255,)), (0, 0),
                  ImageChops.subtract(gap, hole))
    from PIL import ImageChops
    img.paste(Image.new('RGBA', (S, S), fg + (255,)), (0, 0),
              ImageChops.subtract(outer, inner))
    return img


def square(bg, fg, round_=False):
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    mask = Image.new('L', (S, S), 0)
    md = ImageDraw.Draw(mask)
    if round_:
        md.ellipse((0, 0, S - 1, S - 1), fill=255)
    else:
        md.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.22), fill=255)
    base = Image.new('RGBA', (S, S), bg + (255,))
    img.paste(base, (0, 0), mask)
    a = art(fg, 0.95, halo=bg)
    img.alpha_composite(a)
    return img


def save(img, path, px):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.resize((px, px), Image.LANCZOS).save(path)


def main():
    src = (ROOT / 'lib/services/app_icon_service.dart').read_text(encoding='utf-8')
    icons = re.findall(
        r"id: '(\w+)',\s*background: Color\(0x(\w+)\),\s*letters: Color\(0x(\w+)\)", src)
    default_bg, default_fg = hexc('FDE3E2'), hexc('E75480')
    for dens, k in DENS.items():
        leg = int(48 * k)
        save(square(default_bg, default_fg), RES / f'mipmap-{dens}/launcher_icon.png', leg)
        save(square(default_bg, default_fg, True), RES / f'mipmap-{dens}/launcher_icon_round.png', leg)
        save(square(default_bg, default_fg), RES / f'mipmap-{dens}/ic_launcher.png', leg)
        # Адаптивный передний план: 108dp, значимое — в центральных 72dp.
        save(art(default_fg, 0.62, halo=default_bg), RES / f'mipmap-{dens}/launcher_icon_fg.png', int(108 * k))
        for iid, bg, fg in icons:
            if iid == 'default':
                continue
            p = RES / f'mipmap-{dens}/ic_launcher_{iid}.png'
            if not p.exists():
                continue
            save(square(hexc(bg), hexc(fg)), p, leg)
            save(square(hexc(bg), hexc(fg), True), RES / f'mipmap-{dens}/ic_launcher_{iid}_round.png', leg)
    logo = ROOT / 'assets/images/logo'
    square(default_bg, default_fg).resize((512, 512), Image.LANCZOS).save(logo / 'app_icon.webp', 'WEBP', quality=92)
    full = Image.new('RGBA', (S, S), default_bg + (255,))
    full.alpha_composite(art(default_fg, 0.95, halo=default_bg))
    full.convert('RGB').save(logo / 'logo.jpg', quality=92)
    square(default_bg, default_fg).resize((512, 512), Image.LANCZOS).save(ROOT / 'docs/branding/app-icon-512.png')
    print('icons:', len(icons))


if __name__ == '__main__':
    main()
