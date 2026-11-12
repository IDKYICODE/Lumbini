"""After blender/bake.py: encode lightmaps, copy textures for the web, make the sky background.

python tools/post.py
- build/light_<zone>.npy (float irradiance) -> web/assets/light/<zone>.jpg holding sRGB(L / Lmax); Lmax goes into scene.json
- every texture the materials use -> web/assets/tex/ (resized for phones)
- the HDRI -> web/assets/sky.jpg (tone-mapped equirect)
"""
import json, shutil
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT, WEB = ROOT / 'build', ROOT / 'web' / 'assets'
for d in ('light', 'tex'): (WEB / d).mkdir(parents=True, exist_ok=True)
man = json.load(open(WEB / 'scene.json'))
layout = json.load(open(OUT / 'layout.json'))


def srgb(x): return np.where(x <= .0031308, x * 12.92, 1.055 * np.power(np.clip(x, 0, None), 1 / 2.4) - .055)


for zone, z in man['zones'].items():
    z['lmax'] = z['lmax'] if isinstance(z.get('lmax'), dict) else {}
    for mood in z.get('moods', ['day']):
        sfx = '' if mood == 'day' else '_' + mood
        f = OUT / f'light_{zone}{sfx}.npy'
        if not f.exists(): continue
        L = np.clip(np.load(f).astype(np.float32), 0, None)
        lum = L @ np.array([.2126, .7152, .0722], np.float32)
        lmax = float(np.percentile(lum[lum > 1e-4], 99.8)) * 1.1 if (lum > 1e-4).any() else 1.
        s = srgb(np.clip(L / lmax, 0, 1)) + (np.random.default_rng(1).random(L.shape, np.float32) - .5) / 255   # dither
        im = Image.fromarray((np.clip(s[::-1], 0, 1) * 255 + .5).astype(np.uint8))
        im.save(WEB / 'light' / f'{zone}{sfx}.jpg', quality=94, optimize=True)
        im.resize((max(256, im.width // 2), max(256, im.height // 2)), Image.LANCZOS).save(WEB / 'light' / f'{zone}{sfx}_m.jpg', quality=92, optimize=True)   # phones
        z['lmax'][mood] = round(lmax, 4)
        print('light', zone, mood, L.shape[:2], 'Lmax', z['lmax'][mood])

BIG = {'marble.jpg': 2048, 'oak_planks.jpg': 2048, 'mural.jpg': 2048}
for web, src in layout['images'].items():
    dst = WEB / 'tex' / web
    if dst.exists() and dst.stat().st_mtime > Path(src).stat().st_mtime: continue
    im = Image.open(src)
    lim = BIG.get(web, 512 if web.startswith(('leaves', 'jaali')) or '_' in web and not web.endswith(('veneer.jpg', 'tile.jpg')) else 1024)
    im.thumbnail((lim, lim), Image.LANCZOS)
    if web.endswith('.png'): im.save(dst, optimize=True)
    else: im.convert('RGB').save(dst, quality=88, optimize=True)
print('textures', len(layout['images']))

sky = WEB / 'sky.jpg'
if not sky.exists():
    hdr = cv2.imread(str(ROOT / 'assets_src' / 'hdri' / 'kloofendal_48d_partly_cloudy_puresky.hdr'), cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)[..., ::-1]
    x = hdr * .8; x = x / (1 + x * .3)
    Image.fromarray((np.clip(srgb(x), 0, 1) * 255).astype(np.uint8)).resize((4096, 2048), Image.LANCZOS).save(sky, quality=88)
    print('sky')
sky_n = WEB / 'sky_night.jpg'
if not sky_n.exists():     # dusk: deep indigo overhead, a warm afterglow on the horizon, a few early stars
    H, W = 1024, 2048; v = np.linspace(0, 1, H)[:, None]          # 0 = zenith, .5 = horizon
    top, mid, glow, ground = np.array([.03, .045, .11]), np.array([.12, .16, .32]), np.array([.85, .48, .3]), np.array([.03, .035, .04])
    up = np.clip(v / .5, 0, 1)[..., None]
    col = top * (1 - up) + mid * up
    col = col + glow * np.exp(-((v - .5) / .045) ** 2)[..., None] * .8
    col = np.where((v > .5)[..., None], ground, col) * np.ones((1, W, 1))
    r = np.random.default_rng(5); ys, xs = r.integers(0, int(H * .35), 260), r.integers(0, W, 260)
    col[ys, xs] = np.maximum(col[ys, xs], r.uniform(.4, 1, (260, 1)))
    Image.fromarray((np.clip(srgb(col), 0, 1) * 255).astype(np.uint8)).save(sky_n, quality=90)
    print('dusk sky')
shutil.copy(OUT / 'layout.json', WEB / 'layout.json')
json.dump(man, open(WEB / 'scene.json', 'w'), indent=1)
print('scene.json', list(man['zones']))
