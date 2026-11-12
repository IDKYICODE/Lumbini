"""Check plant placement: each plant's real leaf spread against furniture and walls on its floor.

Run:  blender -b build/villa.blend -P blender/check_plants.py
For every plant (plt_* objects, grouped per placement) prints its canopy footprint and anything it overlaps:
furniture (collision boxes of the same floor, except the plant's own box) and walls (canopy outside the floor's walk areas).
"""
import json, sys
from pathlib import Path
import bpy
import numpy as np

ROOT = Path(bpy.data.filepath).parents[1]
L = json.load(open(ROOT / 'build' / 'layout.json'))
LZ = L['levelsZ']
lv_of = lambda z: min(range(len(LZ)), key=lambda i: abs(LZ[i] - z))

# group plant objects into placements (objects of one import share a centre)
groups = {}
for o in bpy.data.objects:
    if not o.name.startswith('plt_'): continue
    v = np.array([o.matrix_world @ p.co for p in o.data.vertices])
    key = (o.name.split('.')[0], round(float(v[:, 0].mean()), 0), round(float(v[:, 1].mean()), 0), round(float(v[:, 2].min()), 1))
    groups.setdefault(key, []).append(v)
bad = 0
for (name, *_), vs in sorted(groups.items()):
    v = np.concatenate(vs); zmin = v[:, 2].min(); lv = lv_of(zmin if zmin > .3 else 0)
    if zmin - LZ[lv] > .5 and lv > 0: print('skip', name, 'on a table / planter'); continue
    leaf = v[v[:, 2] > zmin + .25] if (v[:, 2] > zmin + .25).any() else v
    x0, y0, x1, y1 = np.percentile(leaf[:, 0], 3), np.percentile(leaf[:, 1], 3), np.percentile(leaf[:, 0], 97), np.percentile(leaf[:, 1], 97)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hits = []
    for b in L['block']:
        if b[0] != lv: continue
        bx0, by0, bx1, by1 = b[1:]
        if bx0 - .05 <= cx <= bx1 + .05 and by0 - .05 <= cy <= by1 + .05 and (bx1 - bx0) < 1.0 and (by1 - by0) < 1.0: continue  # own box
        ox, oy = min(x1, bx1) - max(x0, bx0), min(y1, by1) - max(y0, by0)
        if ox > .04 and oy > .04: hits.append(f'furniture[{bx0:.2f},{by0:.2f},{bx1:.2f},{by1:.2f}] by {min(ox, oy):.2f} m')
    def inside(x, y):
        for w in L['walk']:
            if (w[0] == lv or (w[0] is None and lv == 0)) and w[1] <= x <= w[3] and w[2] <= y <= w[4]: return True
        return False
    def reach(tx, ty):
        n = max(2, int(np.hypot(tx - cx, ty - cy) / .04))
        return all(inside(cx + (tx - cx) * i / n, cy + (ty - cy) * i / n) for i in range(n + 1))
    out = [(x, y) for x in (x0, cx, x1) for y in (y0, cy, y1) if not reach(x, y)]
    if lv > 0 and out: hits.append(f'wall/outside at {len(out)} of 9 canopy points')
    print(f'{"BAD " if hits else "ok  "} {name:28s} lv{lv} centre ({cx:.2f}, {cy:.2f}) spread {x1 - x0:.2f} x {y1 - y0:.2f}', '; '.join(hits))
    bad += bool(hits)
print('PLANTS', len(groups), 'BAD', bad)
