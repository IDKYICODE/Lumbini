"""Walkable heightfield computed from the built geometry (replaces hand-entered walk areas and collision boxes).

Run:  blender -b build/villa.blend -P blender/navgrid.py
For every 8 cm column of the site, rays are cast downward through ALL geometry, giving the solid intervals in that
column. A surface is walkable when its top faces up, has 1.9 m of free headroom, can be reached from a teleport spot
by steps of at most 25 cm, and a body of radius 22 cm fits around it. Writes web/assets/nav.bin (gzip) + nav.json:
  K layers of uint16 heights in mm (0 = none), then one uint8 per cell with a 'see across at eye height' bit per level.
Teleport spots that do not sit on walkable floor are moved to the nearest walkable cell (layout.json is updated).
"""
import json, math, gzip, time
from pathlib import Path
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(bpy.data.filepath).parents[1]
OUT, WEB = ROOT / 'build', ROOT / 'web' / 'assets'
L = json.load(open(OUT / 'layout.json')); LZ = L['levelsZ']
CELL, X0, Y0, X1, Y1 = .08, -5.0, -6.0, 21.0, 21.0
HEAD, STEP, RAD, K = 1.9, .25, .22, 4
NX, NY = int(round((X1 - X0) / CELL)), int(round((Y1 - Y0) / CELL))
t0 = time.time()
log = lambda *a: print(f'[nav {time.time() - t0:6.1f}s]', *a, flush=True)

# ---- one BVH of everything solid (tree leaf cards and the sky are ignored)
bm = bmesh.new()
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name.endswith('_fx') or o.name.startswith('sky'): continue
    me = o.data.copy(); me.transform(o.matrix_world); bm.from_mesh(me); bpy.data.meshes.remove(me)
bmesh.ops.triangulate(bm, faces=bm.faces)
tree = BVHTree.FromBMesh(bm)
log('bvh', len(bm.faces), 'triangles')

# ---- per column: solid intervals from the downward hit list
TOP = 14.0
def column(x, y):
    hits, z = [], TOP
    for _ in range(40):
        loc, nor, idx, d = tree.ray_cast(Vector((x, y, z)), Vector((0, 0, -1)))
        if loc is None: break
        hits.append((loc.z, nor.z)); z = loc.z - 1e-4
    # intervals: an up-facing hit opens a solid going down, a down-facing hit closes it; thin faces are 2 cm solids
    solids, open_top = [], None
    for hz, nz in hits:
        if nz > .2:
            if open_top is None: open_top = hz
        elif nz < -.2:
            if open_top is not None: solids.append((hz, open_top)); open_top = None
            else: solids.append((hz - .01, hz + .01))
        else:
            solids.append((hz - .01, hz + .01))
    if open_top is not None: solids.append((open_top - .05, open_top))
    return hits, solids

Hs = np.zeros((K, NY, NX), np.float32); Hs[:] = np.nan
SEE = np.zeros((NY, NX), np.uint8)
for j in range(NY):
    y = Y0 + (j + .5) * CELL
    for i in range(NX):
        x = X0 + (i + .5) * CELL
        hits, solids = column(x, y)
        cands = []
        for hz, nz in hits:
            if nz <= .7: continue
            if any(lo < hz + HEAD and hi > hz + .05 for lo, hi in solids if not (abs(hi - hz) < 1e-3)): continue
            cands.append(hz)
        merged = []                       # stacked finishes (slab, marble, rug) are one floor: keep the top of each stack
        for hz in sorted(cands):
            if merged and hz - merged[-1] < .06: merged[-1] = hz
            else: merged.append(hz)
        for k, hz in enumerate(merged[:K]): Hs[k, j, i] = hz
        for lv, lz in enumerate(LZ):     # can the eye see across this column at this floor's eye height?
            if not any(lo < lz + 1.9 and hi > lz + 1.3 for lo, hi in solids): SEE[j, i] |= 1 << lv
    if j % 40 == 0: log('row', j, '/', NY)

# ---- body radius: a cell stays only if every cell within RAD has a surface within STEP of it
r = int(math.ceil(RAD / CELL)); offs = [(dj, di) for dj in range(-r, r + 1) for di in range(-r, r + 1) if (dj * dj + di * di) * CELL * CELL <= RAD * RAD]
def shifted(a, dj, di):
    out = np.full_like(a, np.nan); ys = slice(max(0, dj), NY + min(0, dj)); yd = slice(max(0, -dj), NY + min(0, -dj))
    xs = slice(max(0, di), NX + min(0, di)); xd = slice(max(0, -di), NX + min(0, -di)); out[yd, xd] = a[ys, xs]; return out
# ---- thin obstacles (glass panes, rails, door leaves) fall between 8 cm columns: cast horizontal rays between
#      neighbouring cells at knee and chest height; a hit removes both cells (the body radius then keeps you clear)
thin = np.zeros_like(Hs, bool)
for j in range(NY):
    y = Y0 + (j + .5) * CELL
    for i in range(NX):
        x = X0 + (i + .5) * CELL
        for k in range(K):
            h = Hs[k, j, i]
            if np.isnan(h): continue
            for dj, di in ((0, 1), (1, 0)):
                jj, ii = j + dj, i + di
                if jj >= NY or ii >= NX: continue
                for kk in range(K):
                    hh = Hs[kk, jj, ii]
                    if np.isnan(hh) or abs(hh - h) > STEP: continue
                    d = Vector((di * CELL, dj * CELL, 0)).normalized()
                    for zz in (max(h, hh) + .35, max(h, hh) + 1.1):
                        if tree.ray_cast(Vector((x, y, zz)), d, CELL)[0] is not None:
                            thin[k, j, i] = thin[kk, jj, ii] = True; break
np.save(OUT / '_nav_raw.npy', Hs); np.save(OUT / '_nav_thin.npy', thin)
Hs[thin] = np.nan
log('thin obstacles', int(thin.sum()), 'cells')
keep = np.ones_like(Hs, bool)
for dj, di in offs:
    nb = np.stack([shifted(Hs[k], dj, di) for k in range(K)])
    for k in range(K):
        ok = np.zeros((NY, NX), bool)
        for kk in range(K):
            with np.errstate(invalid='ignore'): ok |= np.abs(nb[kk] - Hs[k]) <= STEP
        keep[k] &= ok
Hs[~keep] = np.nan
np.save(OUT / '_nav_eroded.npy', Hs)
log('eroded')

# ---- reachable from the teleport spots by steps <= STEP
cell_of = lambda x, y: (int((y - Y0) / CELL), int((x - X0) / CELL))
reach = np.zeros_like(Hs, bool); stack = []
def nearest_walkable(x, y, z):
    j0, i0 = cell_of(x, y); best = None
    for rr in range(0, 40):
        for dj in range(-rr, rr + 1):
            for di in range(-rr, rr + 1):
                if max(abs(dj), abs(di)) != rr: continue
                j, i = j0 + dj, i0 + di
                if not (0 <= j < NY and 0 <= i < NX): continue
                for k in range(K):
                    h = Hs[k, j, i]
                    if not np.isnan(h) and abs(h - z) < .3: best = (j, i, k); break
                if best: break
            if best: break
        if best: return best
    return None
moved = 0
for s in L['spots']:
    z = LZ[s['lv']]; b = nearest_walkable(s['x'], s['y'], z)
    if b is None: log('SPOT unplaceable', s['name']); continue
    j, i, k = b; nx, ny = X0 + (i + .5) * CELL, Y0 + (j + .5) * CELL
    if math.hypot(nx - s['x'], ny - s['y']) > .05: moved += 1; log(f'SPOT {s["name"]} moved {math.hypot(nx - s["x"], ny - s["y"]):.2f} m onto floor')
    s['x'], s['y'] = round(nx, 3), round(ny, 3)
    reach[k, j, i] = True; stack.append((k, j, i))
while stack:
    k, j, i = stack.pop(); h = Hs[k, j, i]
    for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        jj, ii = j + dj, i + di
        if not (0 <= jj < NY and 0 <= ii < NX): continue
        for kk in range(K):
            hh = Hs[kk, jj, ii]
            if not reach[kk, jj, ii] and not np.isnan(hh) and abs(hh - h) <= STEP: reach[kk, jj, ii] = True; stack.append((kk, jj, ii))
Hs[~reach] = np.nan
log('reachable cells', int(reach.sum()))
# which spots can walk to which (stairs connect floors, so ideally one group)
comp = np.zeros(Hs.shape, np.int32); ncomp = 0
for s in L['spots']:
    b = nearest_walkable(s['x'], s['y'], LZ[s['lv']])
    if not b: continue
    j, i, k = b
    if not comp[k, j, i]:
        ncomp += 1; st = [(k, j, i)]; comp[k, j, i] = ncomp
        while st:
            k1, j1, i1 = st.pop(); h = Hs[k1, j1, i1]
            for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                jj, ii = j1 + dj, i1 + di
                if not (0 <= jj < NY and 0 <= ii < NX): continue
                for kk in range(K):
                    hh = Hs[kk, jj, ii]
                    if not comp[kk, jj, ii] and not np.isnan(hh) and abs(hh - h) <= STEP: comp[kk, jj, ii] = ncomp; st.append((kk, jj, ii))
    s['_g'] = int(comp[k, j, i])
groups = {}
for s in L['spots']: groups.setdefault(s.get('_g'), []).append(s['name'])
for s in L['spots']: s.pop('_g', None)
log('WALK GROUPS', len(groups), ' || '.join(', '.join(v) for v in groups.values()))

# ---- write
mm = np.where(np.isnan(Hs), 0, np.clip((Hs + 1.0) * 1000, 1, 65535)).astype('<u2')     # heights stored +1 m so 0 means none
WEB.mkdir(parents=True, exist_ok=True)
open(WEB / 'nav.bin', 'wb').write(gzip.compress(mm.tobytes() + SEE.tobytes(), 9))
json.dump({'cell': CELL, 'x0': X0, 'y0': Y0, 'nx': NX, 'ny': NY, 'k': K, 'offset': 1.0, 'levelsZ': LZ}, open(WEB / 'nav.json', 'w'))
json.dump(L, open(OUT / 'layout.json', 'w'), indent=1)
# a picture of every floor for checking
try:
    import numpy as _np
    for lv, lz in enumerate(LZ):
        img = _np.full((NY, NX, 3), 245, _np.uint8)
        walk = _np.zeros((NY, NX), bool)
        for k in range(K):
            with _np.errstate(invalid='ignore'): walk |= _np.abs(Hs[k] - lz) < 1.2
        img[(SEE >> lv) & 1 == 0] = (205, 205, 205); img[walk] = (140, 205, 140)
        for s in L['spots']:
            if s['lv'] == lv:
                j, i = cell_of(s['x'], s['y']); img[max(0, j - 2):j + 3, max(0, i - 2):i + 3] = (200, 30, 30)
        im = bpy.data.images.new(f'nav{lv}', NX, NY); px = _np.concatenate([img / 255., _np.ones((NY, NX, 1))], 2).astype(_np.float32)
        im.pixels.foreach_set(px.ravel()); im.filepath_raw = str(OUT / f'navgrid_{lv}.png'); im.file_format = 'PNG'; im.save()
except Exception as e:
    log('picture failed', e)
log('done; spots moved', moved, '; nav.bin', (WEB / 'nav.bin').stat().st_size // 1024, 'KB')
