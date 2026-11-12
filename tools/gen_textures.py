"""Generate the original textures the villa needs (numpy + Pillow) into assets_src/gen/.

python tools/gen_textures.py            (all)
python tools/gen_textures.py marble art (only these)
Every tiling texture wraps seamlessly. Grey textures are tinted by the material colour in Blender.
"""
import sys, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'assets_src' / 'gen'; OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE / 'assets_src' / 'tex'
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- noise (periodic, so tiles wrap)
def vnoise(h, w, fy, fx, seed):
    r = np.random.default_rng(seed).random((fy, fx))
    y = np.arange(h)[:, None] * fy / h; x = np.arange(w)[None, :] * fx / w
    iy, ix = np.floor(y).astype(int), np.floor(x).astype(int); ty, tx = y - iy, x - ix
    ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
    a, b = r[iy % fy, ix % fx], r[iy % fy, (ix + 1) % fx]
    c, d = r[(iy + 1) % fy, ix % fx], r[(iy + 1) % fy, (ix + 1) % fx]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def fbm(h, w, f, oct, seed, gain=.5):
    s, amp, tot = 0, 1., 0
    for k in range(oct):
        s = s + amp * vnoise(h, w, f << k, f << k, seed + 31 * k); tot += amp; amp *= gain
    return s / tot


def warp_sample(img, dy, dx):
    """img[y + dy, x + dx] with wrap (nearest)."""
    h, w = img.shape[:2]
    yy = (np.arange(h)[:, None] + dy).astype(int) % h; xx = (np.arange(w)[None, :] + dx).astype(int) % w
    return img[yy, xx]


def save(arr, name, q=90):
    arr = np.clip(arr, 0, 1)
    im = Image.fromarray((arr * 255 + .5).astype(np.uint8))
    p = OUT / name
    im.save(p, quality=q, optimize=True) if name.endswith('.jpg') else im.save(p, optimize=True)
    print('  ', name, im.size)


def hexc(c): return np.array([int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)])


# ---------------------------------------------------------------- textures
def marble():
    """White statuario: soft grey clouding, a few long grey veins and fine hairline veins. One tile = 2.4 m
    (2 x 2 slabs of 1.2 m with hairline joints)."""
    S = 2048
    base = fbm(S, S, 3, 6, 1)
    wx, wy = fbm(S, S, 2, 5, 2) - .5, fbm(S, S, 2, 5, 3) - .5
    y = np.arange(S)[:, None] / S; x = np.arange(S)[None, :] / S
    t = (x * 1.0 + y * 2.0) + wx * 1.6 + wy * .9                     # diagonal vein field, warped
    v1 = np.abs(np.sin(t * math.pi * 3)) ** .08                      # thin dark lines where sin ~ 0
    t2 = (x * 3.0 - y * 1.0) + (fbm(S, S, 4, 5, 9) - .5) * 1.3
    v2 = np.abs(np.sin(t2 * math.pi * 4)) ** .035
    mask = fbm(S, S, 2, 3, 12)                                       # veins fade in and out
    vein = (1 - v1) * np.clip((mask - .38) * 3, 0, 1) * .55 + (1 - v2) * np.clip((mask - .5) * 3, 0, 1) * .28
    L = .93 + (base - .5) * .07 - vein
    col = np.stack([L * .995, L * .99, L * .985], -1)
    col = col + (np.stack([fbm(S, S, 6, 3, 21)] * 3, -1) - .5) * np.array([.02, .015, .0])  # faint warm drift
    for k in (0, S // 2):                                            # slab joints
        col[k:k + 2, :] *= .82; col[:, k:k + 2] *= .82
    save(col, 'marble.jpg', 92)


def planks():
    """Engineered oak, 0.19 m boards, staggered; cut from the Poly Haven oak veneer. One tile = 2.4 m."""
    src = np.asarray(Image.open(SRC / 'oak_veneer_01' / 'diffuse.jpg').convert('RGB').resize((2048, 2048)), np.float32) / 255
    S = 2048; rows = 12; L = S // 2; out = np.zeros_like(src)
    for r in range(rows):
        y0, y1 = r * S // rows, (r + 1) * S // rows
        off = int(rng.integers(0, S))
        for k in range(-1, 3):
            x0 = (k * L + (r * 683) % L)
            sx, sy = int(rng.integers(0, S)), int(rng.integers(0, S))
            tint = 1 + rng.normal(0, .06)
            for xs in range(x0, x0 + L):
                xx = xs % S
                out[y0:y1, xx] = src[(np.arange(y0, y1) + sy) % S, (xs + sx) % S] * tint
            out[y0:y1, x0 % S] *= .55
        out[y0:y0 + 2, :] *= .6
    out = out * .92 + .02
    save(out, 'oak_planks.jpg', 90)


def lawn():
    S = 1024
    n = fbm(S, S, 8, 4, 40); clump = fbm(S, S, 3, 4, 41)
    blades = np.random.default_rng(3).random((S, S))
    blades = Image.fromarray((blades * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6))
    b = np.asarray(blades, np.float32) / 255
    b = (b + warp_sample(b, 1, 0) + warp_sample(b, 2, 0) + warp_sample(b, 3, 1)) / 4    # short vertical strokes
    g = np.clip((b - .5) * 3 + .5, 0, 1)
    dark, light = hexc('#2F5A1E'), hexc('#7BA444')
    k = np.clip(g * .7 + (clump - .5) * .6 + (n - .5) * .3 + .15, 0, 1)[..., None]
    col = dark * (1 - k) + light * k
    save(col, 'lawn.jpg', 90)


def hedge():
    """Clipped boxwood: thousands of small overlapping leaves, dark gaps between them; wraps seamlessly."""
    S = 1024; im = Image.new('RGB', (S, S), (22, 38, 16)); d = ImageDraw.Draw(im); r = np.random.default_rng(11)
    dark, light = hexc('#2C4A1E'), hexc('#7FA052')
    for _ in range(26000):
        x, y = r.random(2) * S; a = r.random() * math.pi; L, W = 9 + r.random() * 7, 4 + r.random() * 3
        k = r.random() ** .8; c = tuple(int(v * 255) for v in dark * (1 - k) + light * k)
        dx, dy = math.cos(a) * L / 2, math.sin(a) * L / 2; nx, ny = -math.sin(a) * W / 2, math.cos(a) * W / 2
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                cx, cy = x + ox, y + oy
                if -20 < cx < S + 20 and -20 < cy < S + 20:
                    d.polygon([(cx - dx, cy - dy), (cx + nx, cy + ny), (cx + dx, cy + dy), (cx - nx, cy - ny)], fill=c)
    save(np.asarray(im, np.float32) / 255, 'hedge.jpg', 90)


def boucle():
    S = 512
    loops = np.random.default_rng(5).random((S // 4, S // 4))
    im = Image.fromarray((loops * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC).filter(ImageFilter.GaussianBlur(.8))
    a = np.asarray(im, np.float32) / 255
    a = .82 + (a - .5) * .28 + (fbm(S, S, 16, 3, 50) - .5) * .12
    save(np.stack([a] * 3, -1), 'boucle.jpg', 90)


def weave():
    S = 512; y = np.arange(S)[:, None]; x = np.arange(S)[None, :]
    w = .5 + .5 * np.sin(x * 2 * math.pi * 96 / S) * np.sin(y * 2 * math.pi * 96 / S)
    a = .84 + .08 * w + (fbm(S, S, 32, 2, 60) - .5) * .1 + (vnoise(S, S, 1, 128, 61) - .5) * .05
    save(np.stack([a] * 3, -1), 'weave.jpg', 90)


def velvet():
    S = 512
    a = .8 + (fbm(S, S, 6, 4, 70) - .5) * .25 + (vnoise(S, S, 256, 256, 71) - .5) * .06
    save(np.stack([a] * 3, -1), 'velvet.jpg', 90)


def carpet_theatre():
    S = 512
    a = .7 + (np.random.default_rng(9).random((S, S)) - .5) * .25 + (fbm(S, S, 8, 3, 72) - .5) * .15
    col = np.stack([a] * 3, -1) * hexc('#3A2A24')
    save(col / col.max() * .55, 'carpet_dark.jpg', 90)


def rug(name, bg, ink, kind):
    W, H = 1600, 1100
    S = max(W, H)
    n = fbm(S, S, 4, 5, 80 + len(name))[:H, :W]
    if kind == 'cloud':                       # grey abstract, like the master bedroom rug in the film
        k = np.clip((fbm(S, S, 2, 6, 81)[:H, :W] - .35) * 2.2, 0, 1)
        col = hexc(bg) * (1 - k[..., None]) + hexc(ink) * k[..., None]
    else:                                     # lines / borders
        col = np.ones((H, W, 3)) * hexc(bg)
        im = Image.fromarray((col * 255).astype(np.uint8)); d = ImageDraw.Draw(im)
        c = tuple(int(v * 255) for v in hexc(ink))
        d.rectangle([60, 60, W - 61, H - 61], outline=c, width=10)
        d.rectangle([100, 100, W - 101, H - 101], outline=c, width=3)
        for i in range(9):
            r = 120 + i * 55; d.arc([W * .62 - r, H * .5 - r, W * .62 + r, H * .5 + r], 200, 330, fill=c, width=4)
        col = np.asarray(im, np.float32) / 255
    col = col * (.92 + (n[..., None] - .5) * .16)
    fib = np.random.default_rng(83).random((H, W, 1)) * .06
    save(col - fib, f'rug_{name}.jpg', 90)


def mural():
    """Chinoiserie-style wall mural (original): misty layered hills, a blossoming branch and birds on warm silk."""
    W, H = 3000, 1100
    y = np.linspace(0, 1, H)[:, None]; x = np.linspace(0, 1, W)[None, :]
    silk = hexc('#E9DCC2') * (1 - y[..., None] * .25) + hexc('#D8C4A0') * (y[..., None] * .25)
    col = silk * (.94 + (fbm(H, H, 6, 5, 90)[:, :1].repeat(W, 1)[..., None] - .5) * .05)
    for li, (lev, amp, c, a) in enumerate([(.55, .18, '#B9B39A', .45), (.66, .16, '#9C9C84', .55), (.78, .14, '#7E8670', .7), (.9, .08, '#5F6B55', .85)]):
        ridge = np.array([lev - amp * (fbm(1, 1024, 3 + li, 5, 91 + li)[0, int(i * 1023 / (W - 1))] - .3) for i in range(W)])
        m = (y > ridge[None, :]).astype(np.float32)
        fade = np.clip((y - ridge[None, :]) * 6, 0, 1)
        k = (m * a * (1 - .55 * fade))[..., None]
        col = col * (1 - k) + hexc(c) * k
    im = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)); d = ImageDraw.Draw(im)
    r = np.random.default_rng(92)
    def branch(x0, y0, ang, length, width, depth):
        if depth == 0 or length < 18: return
        x1, y1 = x0 + math.cos(ang) * length, y0 + math.sin(ang) * length
        d.line([x0, y0, x1, y1], fill=(78, 58, 40), width=max(1, int(width)))
        if depth <= 3:
            for _ in range(3):
                bx, by = x0 + (x1 - x0) * r.random(), y0 + (y1 - y0) * r.random()
                rr = r.uniform(6, 13); col2 = (226, int(r.uniform(160, 190)), int(r.uniform(160, 185)))
                d.ellipse([bx - rr, by - rr, bx + rr, by + rr], fill=col2)
                d.ellipse([bx - 3, by - 3, bx + 3, by + 3], fill=(190, 140, 60))
        for s in (-1, 1):
            branch(x1, y1, ang + s * r.uniform(.25, .6), length * r.uniform(.62, .78), width * .7, depth - 1)
    branch(-20, 140, .35, 420, 22, 7); branch(W + 20, 260, math.pi - .4, 380, 18, 7)
    for i in range(7):                                   # birds
        bx, by, s = r.uniform(900, 2300), r.uniform(120, 420), r.uniform(10, 18)
        d.arc([bx - s, by - s * .6, bx, by + s * .6], 200, 340, fill=(70, 62, 52), width=3)
        d.arc([bx, by - s * .6, bx + s, by + s * .6], 200, 340, fill=(70, 62, 52), width=3)
    im = im.filter(ImageFilter.GaussianBlur(.7))
    a = np.asarray(im, np.float32) / 255
    a = a * (.96 + (np.random.default_rng(93).random((H, W, 1)) - .5) * .04)
    save(a, 'mural.jpg', 90)


def art(i):
    """Framed artworks (originals): gold botanicals, earth-tone abstracts, a line drawing."""
    W, H = 700, 900
    r = np.random.default_rng(100 + i)
    bg = [(240, 233, 220), (236, 226, 210), (244, 240, 232), (52, 48, 44)][i]
    im = Image.new('RGB', (W, H), bg); d = ImageDraw.Draw(im)
    if i in (0, 1):            # gold flowers on long stems
        for k in range(3 if i == 0 else 4):
            sx = W * (.3 + .2 * k) + r.uniform(-30, 30); top = H * r.uniform(.18, .4)
            d.line([sx, H * .95, sx + r.uniform(-40, 40), top], fill=(150, 112, 60), width=4)
            for p in range(9):
                a = p / 9 * 2 * math.pi + r.random() * .3; L = r.uniform(70, 120)
                px, py = sx + math.cos(a) * L * .5, top + math.sin(a) * L * .5
                d.ellipse([px - L * .32, py - L * .14, px + L * .32, py + L * .14], fill=(int(r.uniform(196, 220)), int(r.uniform(158, 176)), int(r.uniform(96, 120))))
            d.ellipse([sx - 14, top - 14, sx + 14, top + 14], fill=(120, 84, 44))
    elif i == 2:               # earth circles
        for k in range(5):
            cx, cy, rr = r.uniform(.2, .8) * W, r.uniform(.2, .8) * H, r.uniform(80, 220)
            c = [(196, 112, 78), (212, 170, 120), (122, 98, 80), (230, 200, 160), (160, 82, 60)][k]
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=c)
        d.line([0, H * .62, W, H * .55], fill=(60, 50, 44), width=5)
    else:                      # gold line drawing on charcoal
        pts = [(W * .5 + 220 * math.sin(t * 1.3) * math.cos(t * .4), H * .5 + 300 * math.sin(t * .9)) for t in np.linspace(0, 9, 400)]
        d.line(pts, fill=(205, 168, 104), width=4, joint='curve')
    im = im.filter(ImageFilter.GaussianBlur(.6))
    a = np.asarray(im, np.float32) / 255
    a = a * (.97 + (np.random.default_rng(110 + i).random((H, W, 1)) - .5) * .05)
    save(a, f'art{i}.jpg', 90)


def screen():
    """What plays on the theatre screen / TV: a calm forest dawn (matches 'forest of tranquility')."""
    W, H = 1600, 900
    y = np.linspace(0, 1, H)[:, None, None]
    sky = hexc('#F6D9A8') * (1 - y) + hexc('#8FB3A1') * y
    col = np.broadcast_to(sky, (H, W, 3)).copy()
    for li, (lev, c) in enumerate([(.45, '#6E8F6A'), (.58, '#45684A'), (.72, '#2D4A33'), (.86, '#1D3022')]):
        ridge = lev - .12 * fbm(1, 1024, 4 + 2 * li, 5, 120 + li)[0, (np.arange(W) * 1023 // (W - 1))]
        m = (np.linspace(0, 1, H)[:, None] > ridge[None, :])[..., None]
        col = np.where(m, hexc(c), col)
    sun = np.exp(-(((np.arange(W)[None, :] - W * .62) / 90) ** 2 + ((np.arange(H)[:, None] - H * .36) / 90) ** 2))[..., None]
    col = col + sun * np.array([.6, .45, .2])
    save(col, 'screen.jpg', 88)


def leaves(name, kind):
    """Alpha leaf cluster for the garden trees: 'green' foliage or 'pink' tabebuia blossom."""
    S = 512; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); r = np.random.default_rng(130 + len(name))
    for _ in range(260 if kind == 'green' else 340):
        cx, cy = r.normal(S / 2, S / 5.5), r.normal(S / 2, S / 5.5)
        if (cx - S / 2) ** 2 + (cy - S / 2) ** 2 > (S * .46) ** 2: continue
        L = r.uniform(18, 34) if kind == 'green' else r.uniform(9, 16); a = r.uniform(0, math.pi)
        if kind == 'green':
            g = int(r.uniform(70, 140)); c = (int(g * .45), g, int(g * .3), 255)
        else:
            c = (int(r.uniform(205, 240)), int(r.uniform(90, 140)), int(r.uniform(150, 190)), 255) if r.random() > .15 else (90, 120, 60, 255)
        pts = [(cx + math.cos(a) * L, cy + math.sin(a) * L), (cx + math.cos(a + 1.9) * L * .38, cy + math.sin(a + 1.9) * L * .38),
               (cx - math.cos(a) * L, cy - math.sin(a) * L), (cx + math.cos(a - 1.9) * L * .38, cy + math.sin(a - 1.9) * L * .38)]
        d.polygon(pts, fill=c)
    im.save(OUT / f'leaves_{name}.png', optimize=True); print('  ', f'leaves_{name}.png')


def jaali():
    """Facade screen from the film: grey panel, square cells with triangular voids. One tile = 0.9 m (3 x 3 cells)."""
    S = 768; C = S // 3; im = Image.new('RGBA', (S, S), (122, 124, 124, 255)); d = ImageDraw.Draw(im)
    for i in range(3):
        for j in range(3):
            x0, y0, m = i * C, j * C, C * .16
            a, b, c, e = (x0 + m, y0 + m), (x0 + C - m, y0 + m), (x0 + C - m, y0 + C - m), (x0 + m, y0 + C - m)
            tri = [a, b, e] if (i + j) % 2 else [b, c, a]
            d.polygon(tri, fill=(0, 0, 0, 0))
            d.line([*tri, tri[0]], fill=(96, 98, 98, 255), width=3)
    im.save(OUT / 'jaali.png', optimize=True); print('   jaali.png')


def fluted():
    """Fluted panel (bedroom headboard wall): soft vertical grooves every 4 cm. One tile = 0.48 m."""
    S = 512; x = np.arange(S)[None, :] / S * 12
    g = .86 + .1 * np.abs(np.sin(x * math.pi)) ** .6 - .12 * (np.abs(np.sin(x * math.pi)) < .12)
    a = np.broadcast_to(g, (S, S)) * (.98 + (fbm(S, S, 8, 3, 140) - .5) * .04)
    save(np.stack([a] * 3, -1), 'fluted.jpg', 90)


def stars():
    """Theatre fibre-optic star ceiling."""
    S = 1024; a = np.zeros((S, S, 3)); r = np.random.default_rng(150)
    for _ in range(900):
        x, y, b = r.integers(0, S), r.integers(0, S), r.uniform(.3, 1)
        a[y, x] = b; a[(y + 1) % S, x] = b * .35; a[y, (x + 1) % S] = b * .35
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6)), np.float32) / 255 * 3
    save(a + .04, 'stars.jpg', 92)


JOBS = {
    'jaali': jaali, 'fluted': fluted, 'stars': stars,
    'marble': marble, 'planks': planks, 'lawn': lawn, 'boucle': boucle, 'weave': weave, 'velvet': velvet,
    'carpet': carpet_theatre, 'mural': mural, 'screen': screen,
    'rug': lambda: (rug('cloud', '#D8D6D1', '#8E8C88', 'cloud'), rug('living', '#5B5650', '#9A8F80', 'lines'), rug('lounge', '#CBB89C', '#8A6F4E', 'lines')),
    'art': lambda: [art(i) for i in range(4)],
    'hedge': hedge,
    'leaves': lambda: (leaves('green', 'green'), leaves('pink', 'pink')),
}
for k in (sys.argv[1:] or JOBS):
    print(k); JOBS[k]()
