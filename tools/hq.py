"""High-quality web assets for capable phones and desktops (run after tools/post.py).

python tools/hq.py [--force]
- full-resolution lightmaps (from build/light_*.npy) -> web/assets/hq/light/<zone>[_night].ktx2
- surface textures at up to 2048 px                    -> web/assets/hq/tex/<name>.ktx2
- relief (normal) maps derived from each tiling surface's own detail -> web/assets/hq/tex/<name>_n.ktx2
All are Basis Universal UASTC in KTX2 (+ zstd): the phone's GPU keeps them compressed (ASTC on Android,
BC7 on desktop), about 4x less graphics memory than JPG/PNG. web/assets/hq/hq.json lists what exists.
Needs toktx (KTX-Software, Khronos) - set TOKTX or install to %LOCALAPPDATA%/KTX-Software.
"""
import json, os, subprocess, sys
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT, WEB = ROOT / 'build', ROOT / 'web' / 'assets'
HQ = WEB / 'hq'; TMP = OUT / '_hq'
for d in (HQ / 'light', HQ / 'tex', TMP): d.mkdir(parents=True, exist_ok=True)
TOKTX = os.environ.get('TOKTX') or str(Path(os.environ.get('LOCALAPPDATA', '')) / 'KTX-Software' / 'bin' / 'toktx.exe')
FORCE = '--force' in sys.argv
man = json.load(open(WEB / 'scene.json'))
layout = json.load(open(OUT / 'layout.json'))

# tiling surfaces that get a relief map: name -> (strength, blur px of the height source)
RELIEF = {'oak_planks.jpg': (3., 1), 'walnut_veneer.jpg': (2., 1), 'teak_veneer.jpg': (2., 1), 'oak_veneer_01.jpg': (2., 1),
          'wood_floor_deck.jpg': (4., 1), 'granite_tile.jpg': (3., 1), 'terrazzo_tiles.jpg': (2.5, 1), 'stone_tile_wall.jpg': (5., 2),
          'concrete_pavers.jpg': (5., 2), 'rough_concrete.jpg': (4., 1), 'brown_leather.jpg': (4., 1), 'boucle.jpg': (6., 1),
          'weave.jpg': (5., 1), 'velvet.jpg': (2., 1), 'fluted.jpg': (6., 3), 'carpet_dark.jpg': (4., 1), 'hedge.jpg': (5., 1),
          'lawn.jpg': (3., 1), 'marble.jpg': (.6, 2)}
BIG = 2048          # tiling surfaces and rugs / art
SMALL = 1024        # props and plants (vertex-lit, seen up close less)


def stale(dst, *srcs): return FORCE or not dst.exists() or any(dst.stat().st_mtime < Path(s).stat().st_mtime for s in srcs)


def toktx(dst, png, srgb=True, wrap=True, quality=2, rdo=1.):
    """wrap: tiling texture - mip levels made here by 2x2 box averaging (exact for power-of-two sizes, so tiles stay
    seamless; toktx's --wmode is broken in 4.4.2). Otherwise toktx generates them (clamped)."""
    args = [TOKTX, '--t2', '--encode', 'uastc', '--uastc_quality', str(quality), '--zcmp', '18',
            '--assign_oetf', 'srgb' if srgb else 'linear']
    if rdo: args += ['--uastc_rdo_l', str(rdo)]
    if not srgb: args += ['--assign_primaries', 'none']
    if not wrap:
        files = [png]; args += ['--genmipmap']
    else:
        im = Image.open(png); files = []; lv = 0
        while True:
            f = Path(png).with_name(Path(png).stem + f'_mip{lv}.png'); im.save(f); files.append(f)
            if im.width == 1 and im.height == 1: break
            im = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.BOX); lv += 1
        args += ['--mipmap']
    r = subprocess.run(args + [str(dst)] + [str(f) for f in files], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f'toktx failed for {png}: {r.stderr[-400:]}')


def srgb(x): return np.where(x <= .0031308, x * 12.92, 1.055 * np.power(np.clip(x, 0, None), 1 / 2.4) - .055)


# ---------------------------------------------------------------- lightmaps at full resolution
lights = []
for zone, z in man['zones'].items():
    for mood in z.get('moods', ['day']):
        sfx = '' if mood == 'day' else '_' + mood
        f = OUT / f'light_{zone}{sfx}.npy'; dst = HQ / 'light' / f'{zone}{sfx}.ktx2'
        if not f.exists(): continue
        lights.append(f'{zone}{sfx}')
        if not stale(dst, f): continue
        L = np.clip(np.load(f).astype(np.float32), 0, None)
        lmax = z['lmax'][mood]                                   # same scale as the JPG (post.py), so intensities match
        s = srgb(np.clip(L / lmax, 0, 1)) + (np.random.default_rng(1).random(L.shape, np.float32) - .5) / 255
        png = TMP / f'light_{zone}{sfx}.png'
        Image.fromarray((np.clip(s[::-1], 0, 1) * 255 + .5).astype(np.uint8)).save(png)
        toktx(dst, png, wrap=False, rdo=.5)                      # light RDO: smooth gradients must not band
        print('light', zone, mood, L.shape[:2], round(dst.stat().st_size / 1e6, 1), 'MB')


# ---------------------------------------------------------------- surface textures + relief maps
def normal_from(img, strength, blur):
    """Height = local detail of the albedo (low frequencies removed), Sobel -> tangent-space normal (+v = image down)."""
    g = np.asarray(img.convert('L'), np.float32) / 255
    H, W = g.shape; P = max(H, W) // 8                       # filters on a wrap-padded copy keep the tile seamless
    gp = np.pad(g, P, mode='wrap')
    big = cv2.GaussianBlur(gp, (0, 0), max(H, W) / 64)
    h = cv2.GaussianBlur(gp - big, (0, 0), blur)
    h = h / (np.percentile(np.abs(h[P:-P, P:-P]), 99) + 1e-6)
    k = strength * max(H, W) / 1024
    dx = (cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3) / 8 * k)[P:-P, P:-P]
    dy = (cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3) / 8 * k)[P:-P, P:-P]
    h = h[P:-P, P:-P]
    n = np.dstack([-dx, -dy, np.ones_like(h)]); n /= np.linalg.norm(n, axis=2, keepdims=True)
    return Image.fromarray(((n * .5 + .5) * 255 + .5).astype(np.uint8))


texs, normals = [], []
for web, src in layout['images'].items():
    name = web.rsplit('.', 1)[0]
    dst = HQ / 'tex' / f'{name}.ktx2'
    texs.append(web)
    if web in RELIEF: normals.append(web)
    if not stale(dst, src) and (web not in RELIEF or not stale(HQ / 'tex' / f'{name}_n.ktx2', src)): continue
    im = Image.open(src); alpha = im.mode in ('RGBA', 'LA', 'P') and web.endswith('.png')
    im = im.convert('RGBA' if alpha else 'RGB')
    lim = BIG if ('_' not in web or web.endswith(('veneer.jpg', 'tile.jpg', 'tiles.jpg', 'wall.jpg', 'pavers.jpg', 'concrete.jpg', 'leather.jpg', 'planks.jpg', 'deck.jpg', '_01.jpg'))) else SMALL
    im.thumbnail((lim, lim), Image.LANCZOS)
    w, h = (1 << (im.width - 1).bit_length(), 1 << (im.height - 1).bit_length())      # power of two: mipmaps + wrap everywhere
    w, h = min(w, lim), min(h, lim)
    if (w, h) != im.size: im = im.resize((w, h), Image.LANCZOS)
    png = TMP / f'{name}.png'; im.save(png)
    toktx(dst, png)
    if web in RELIEF:
        nimg = normal_from(im, *RELIEF[web])
        if max(nimg.size) > 1024: nimg = nimg.resize((min(1024, nimg.width), min(1024, nimg.height)), Image.LANCZOS)
        npng = TMP / f'{name}_n.png'; nimg.save(npng)
        toktx(HQ / 'tex' / f'{name}_n.ktx2', npng, srgb=False, rdo=0)
    print('tex', web, im.size, round(dst.stat().st_size / 1e6, 2), 'MB', '+ relief' if web in RELIEF else '')

json.dump({'lights': lights, 'tex': [t.rsplit('.', 1)[0] for t in texs], 'relief': [t.rsplit('.', 1)[0] for t in normals]},
          open(HQ / 'hq.json', 'w'), indent=1)
tot = sum(p.stat().st_size for p in HQ.rglob('*.ktx2'))
print('hq assets', round(tot / 1e6, 1), 'MB')
