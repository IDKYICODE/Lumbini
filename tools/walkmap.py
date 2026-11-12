"""Draw each floor's walkable plan (what the viewer lets you walk on) and audit it.

python tools/walkmap.py  -> build/walkmap_<level>.png + a report
Green: floor you can stand on (body radius 0.22 m respected). Red: furniture/collision boxes. Blue: stairs.
Grey: walk rectangles. Dots: teleport spots. The report lists spots that cannot reach each other on foot.
"""
import json, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
L = json.load(open(ROOT / 'build' / 'layout.json'))
LZ = L['levelsZ']; R, STEP, CELL = .22, .42, .05
X0, Y0, X1, Y1 = -2, -6, 18, 19
W, H = int((X1 - X0) / CELL), int((Y1 - Y0) / CELL)

surf = [(w[1:5], (w[5] if len(w) > 5 else LZ[w[0]]), None) for w in L['walk']]
for rp in L['ramps']:
    surf.append((rp['r'], None, rp))
def z_of(s, x, y):
    r, z, rp = s
    if rp is None: return z
    x0, y0, x1, y1 = rp['r']; ax = rp['axis'].replace('-', ''); neg = rp['axis'][0] == '-'
    t = (x - x0) / (x1 - x0) if ax == 'x' else (y - y0) / (y1 - y0); t = min(1, max(0, 1 - t if neg else t))
    return rp['z0'] + (rp['z1'] - rp['z0']) * t
def surface(x, y, zn):
    best = None
    for s in surf:
        r = s[0]
        if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
            z = z_of(s, x, y)
            if abs(z - zn) <= STEP and (best is None or z > best): best = z
    return best
lv_of = lambda z: min(range(len(LZ)), key=lambda i: abs(LZ[i] - z))
def blocked(x, y, z):
    for b in L['block']:
        if b[0] != lv_of(z): continue
        if b[1] - R < x < b[3] + R and b[2] - R < y < b[4] + R: return True
    return False
def stand(x, y, zn):
    z = surface(x, y, zn)
    if z is None: return None
    for k in range(8):
        a = k * math.pi / 4
        if surface(x + math.cos(a) * R, y + math.sin(a) * R, z) is None: return None
    return None if blocked(x, y, z) else z

report = []
spots = L['spots']
for lv, lz in enumerate(LZ):
    im = Image.new('RGB', (W, H), (250, 250, 248)); d = ImageDraw.Draw(im)
    P = lambda x, y: ((x - X0) / CELL, (Y1 - y) / CELL)
    for w in L['walk']:
        z = w[5] if len(w) > 5 else LZ[w[0]]
        if lv_of(z) == lv: d.rectangle([P(w[1], w[4]), P(w[3], w[2])], outline=(170, 170, 170))
    ok = np.zeros((H, W), bool)
    for j in range(H):
        for i in range(W):
            x, y = X0 + (i + .5) * CELL, Y1 - (j + .5) * CELL
            z = stand(x, y, lz)
            if z is not None and lv_of(z) == lv: ok[j, i] = True
    px = np.asarray(im).copy(); px[ok] = (150, 215, 150); im = Image.fromarray(px); d = ImageDraw.Draw(im)
    for b in L['block']:
        if b[0] == lv: d.rectangle([P(b[1], b[4]), P(b[3], b[2])], outline=(210, 60, 60))
    for rp in L['ramps']:
        r = rp['r']; d.rectangle([P(r[0], r[3]), P(r[2], r[1])], outline=(60, 90, 220))
    # connectivity between spots of this level (flood fill on the standable grid)
    lab = np.zeros((H, W), np.int32); n = 0
    for j in range(H):
        for i in range(W):
            if ok[j, i] and not lab[j, i]:
                n += 1; st = [(j, i)]; lab[j, i] = n
                while st:
                    a, b = st.pop()
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        aa, bb = a + da, b + db
                        if 0 <= aa < H and 0 <= bb < W and ok[aa, bb] and not lab[aa, bb]: lab[aa, bb] = n; st.append((aa, bb))
    for s in spots:
        if s['lv'] != lv: continue
        i, j = int((s['x'] - X0) / CELL), int((Y1 - s['y']) / CELL)
        c = lab[j, i]; s['_comp'] = int(c)
        d.ellipse([i - 5, j - 5, i + 5, j + 5], fill=(30, 30, 30) if c else (230, 0, 0)); d.text((i + 7, j - 6), s['name'], fill=(20, 20, 20))
        if not c: report.append(f'L{lv}: spot "{s["name"]}" stands where you cannot stand')
    comps = {}
    for s in spots:
        if s['lv'] == lv and s.get('_comp'): comps.setdefault(s['_comp'], []).append(s['name'])
    if len(comps) > 1: report.append(f'L{lv}: separate walkable islands: ' + ' | '.join(', '.join(v) for v in comps.values()))
    im.crop((int((-.5 - X0) / CELL), int((Y1 - 18.5) / CELL), int((16.5 - X0) / CELL), int((Y1 + 5.5) / CELL) if lv == 0 else int((Y1 - .5) / CELL))).save(ROOT / 'build' / f'walkmap_{lv}.png')
print('\n'.join(report) or 'all spots on each floor are connected')
