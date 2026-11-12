"""Shared helpers for building the villa in Blender (headless).

Geometry is accumulated per zone (exterior / ground / first / second) instead of creating thousands of
objects: every primitive is built in a small bmesh (bevel included), moved by the current frame matrix,
given world-scale UVs (or 0..1 'fit' UVs for pictures), then appended to the zone's vertex/face lists.
finish() turns each zone into one mesh object with one material slot per material it uses.

Materials carry the data the web viewer needs as custom properties (exported as glTF extras):
  k     kind: std | emit | glass | water | alpha
  tex   texture file name in web/tex/ (shared by all zones)
  tint  hex colour multiplied with the texture (or the flat colour)
  gloss 0..1 reflection strength in the viewer
  emit  hex colour, es emission strength
Coordinates: metres, x east, y north, z up.
"""
import math, json, shutil, re
from pathlib import Path
from contextlib import contextmanager
import bpy, bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SRC, GEN, OUT = ROOT / 'assets_src', ROOT / 'assets_src' / 'gen', ROOT / 'build'
OUT.mkdir(exist_ok=True)


# ---------------------------------------------------------------- scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'; sc.render.engine = 'CYCLES'
    gpu()
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    return sc


def gpu():
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = kind; prefs.get_devices()
            if any(d.type == kind for d in prefs.devices): break
        except TypeError:
            pass
    for d in prefs.devices: d.use = True
    bpy.context.scene.cycles.device = 'GPU'


def lin(hexc):
    rgb = tuple(int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb)


# ---------------------------------------------------------------- materials
_mats = {}
IMAGES = {}            # web name -> source path (copied to web/tex by the bake step)


def tex_path(name):
    """'marble.jpg' (generated) or 'walnut_veneer' (Poly Haven, diffuse)."""
    p = GEN / name
    if p.exists(): return p
    return SRC / 'tex' / name / 'diffuse.jpg'


def mat(name, color='#FFFFFF', rough=.6, metal=0., tex=None, tile=1., emit=None, es=0., kind='std', gloss=0., alpha=None, double=False):
    """tile: metres per texture repeat (number or (u, v)). alpha: texture with alpha (leaves)."""
    if name in _mats: return _mats[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; p = nt.nodes['Principled BSDF']
    L = lin(color)
    p.inputs['Base Color'].default_value = (*L, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    m['k'] = kind; m['tint'] = color; m['gloss'] = gloss; m['tile'] = list(tile) if isinstance(tile, (tuple, list)) else [tile, tile]
    if tex:
        path = tex_path(tex) if not isinstance(tex, Path) else tex
        web = (tex if isinstance(tex, str) and tex.endswith(('.jpg', '.png')) else f'{tex}.jpg') if not isinstance(tex, Path) else path.name
        IMAGES[web] = path; m['tex'] = web
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(str(path), check_existing=True)
        uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'; nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1
        nt.links.new(t.outputs['Color'], mix.inputs['A']); mix.inputs['B'].default_value = (*L, 1)
        nt.links.new(mix.outputs['Result'], p.inputs['Base Color'])
        if alpha:
            nt.links.new(t.outputs['Alpha'], p.inputs['Alpha'])
            m['k'] = 'alpha' if kind == 'alpha' else 'cut'     # cut: alpha-tested but lightmapped
    if emit:
        p.inputs['Emission Color'].default_value = (*lin(emit), 1); p.inputs['Emission Strength'].default_value = es
        m['emit'] = emit; m['es'] = es
    if kind == 'glass':
        p.inputs['Transmission Weight'].default_value = 1; p.inputs['Roughness'].default_value = 0
    m.use_backface_culling = not double
    _mats[name] = m
    return m


# ---------------------------------------------------------------- zones + accumulation
class Zone:
    def __init__(self, name):
        self.name = name; self.V = []; self.F = []; self.UV = []; self.FM = []; self.mats = []; self.mi = {}

    def mat_index(self, m):
        if m.name not in self.mi: self.mi[m.name] = len(self.mats); self.mats.append(m)
        return self.mi[m.name]


ZONES = {}
_zone = ['ext']
_frame = [Matrix.Identity(4)]
FX_KINDS = ('glass', 'water', 'emit', 'alpha')   # kept out of the lightmap (own object per zone)


def _suffix(kind):
    """glass/water: hidden while baking; emit/alpha: lit-up or cut-out, not lightmapped."""
    return '_glass' if kind in ('glass', 'water') else '_fx' if kind in ('emit', 'alpha') else ''


def Z(name=None):
    n = name or _zone[-1]
    key = n
    if key not in ZONES: ZONES[key] = Zone(key)
    return ZONES[key]


@contextmanager
def zone(name):
    _zone.append(name)
    try: yield
    finally: _zone.pop()


@contextmanager
def frame(x=0., y=0., z=0., rot=0.):
    """Local frame: everything inside is rotated `rot` degrees about z (counter-clockwise) and moved to (x, y, z)."""
    M = _frame[-1] @ Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(rot), 4, 'Z')
    _frame.append(M)
    try: yield
    finally: _frame.pop()


def _emit(bm, m, uvmode='world', rot_uv=False):
    """Append bmesh geometry (local coords) to the current zone."""
    M = _frame[-1]
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    bm.normal_update()
    kind = m.get('k', 'std')
    zn = _zone[-1] + _suffix(kind)
    zo = Z(zn); base = len(zo.V); mi = zo.mat_index(m)
    tu, tv = m.get('tile', [1, 1])
    zo.V.extend(tuple(v.co) for v in bm.verts)
    if uvmode == 'fit':
        lo = [min(v.co[i] for v in bm.verts) for i in range(3)]; hi = [max(v.co[i] for v in bm.verts) for i in range(3)]
        sz = [max(hi[i] - lo[i], 1e-6) for i in range(3)]
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[ax]
        flip = (ax == 0 and n[0] < 0) or (ax == 1 and n[1] > 0)
        zo.F.append(tuple(base + v.index for v in f.verts)); zo.FM.append(mi)
        for l in f.loops:
            co = l.vert.co
            if uvmode == 'fit':
                u, v = (co[a] - lo[a]) / sz[a], (co[b] - lo[b]) / sz[b]
                if flip: u = 1 - u
            else:
                u, v = co[a] / tu, co[b] / tv
                if flip: u = -u
            zo.UV.append((v, u) if rot_uv else (u, v))
    bm.free()


def _bm_box(w, d, h):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=(w, d, h), verts=bm.verts)
    return bm


def box(x0, y0, z0, x1, y1, z1, m, bevel=0., seg=1, uv='world', rot_uv=False, block=None):
    """Axis-aligned (in the current frame) box. block: level index -> footprint stops the visitor."""
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    w, d, h = x1 - x0, y1 - y0, z1 - z0
    if w < 1e-5 or d < 1e-5 or h < 1e-5: return
    bm = _bm_box(w, d, h)
    if bevel > 0:
        bevel = min(bevel, w / 2.01, d / 2.01, h / 2.01)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=seg, profile=.5, affect='EDGES', clamp_overlap=True)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    if block is not None: blockrect(block, x0, y0, x1, y1)
    _emit(bm, m, uv, rot_uv)


def cyl(x, y, z0, z1, r, m, verts=24, r2=None, uv='world', block=None, cap=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=z1 - z0)
    bmesh.ops.translate(bm, vec=(x, y, (z0 + z1) / 2), verts=bm.verts)
    if block is not None: blockrect(block, x - r, y - r, x + r, y + r)
    _emit(bm, m, uv)


def sphere(x, y, z, r, m, sz=1., segs=20, rings=12):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bmesh.ops.scale(bm, vec=(1, 1, sz), verts=bm.verts); bmesh.ops.translate(bm, vec=(x, y, z), verts=bm.verts)
    _emit(bm, m)


def lathe(x, y, z, profile, m, segs=32):
    """profile: [(radius, height), ...] from bottom to top; revolved about z."""
    bm = bmesh.new(); rings = []
    for (r, h) in profile:
        rings.append([bm.verts.new((x + r * math.cos(2 * math.pi * i / segs), y + r * math.sin(2 * math.pi * i / segs), z + h)) for i in range(segs)])
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], a[j], b[j], b[i]))
    _emit(bm, m)


def tube(points, r, m, segs=10):
    """Round tube along a polyline of (x, y, z)."""
    bm = bmesh.new(); rings = []
    P = [Vector(p) for p in points]
    for i, p in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < .9 else Vector((1, 0, 0))
        u = t.cross(a).normalized(); v = t.cross(u)
        rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * k / segs) + v * math.sin(2 * math.pi * k / segs)) * r) for k in range(segs)])
    for a, b in zip(rings, rings[1:]):
        for k in range(segs):
            j = (k + 1) % segs; bm.faces.new((a[k], a[j], b[j], b[k]))
    _emit(bm, m)


def prism(poly, z0, z1, m, uv='world', block=None):
    """Extrude a 2D polygon [(x, y), ...] (counter-clockwise) from z0 to z1."""
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in poly]; top = [bm.verts.new((x, y, z1)) for x, y in poly]
    bm.faces.new(list(reversed(bot))); bm.faces.new(top)
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n; bm.faces.new((bot[i], bot[j], top[j], top[i]))
    if block is not None:
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]; blockrect(block, min(xs), min(ys), max(xs), max(ys))
    _emit(bm, m, uv)


def quad(pts, m, uv='fit'):
    """One flat face through 4 points (counter-clockwise seen from the front)."""
    bm = bmesh.new(); bm.faces.new([bm.verts.new(p) for p in pts]); _emit(bm, m, uv)


def picture(axis, at, a0, a1, z0, z1, m, facing=1, inset=.0):
    """A flat 0..1-mapped picture on a wall. axis 'x': wall plane x=at spanning y a0..a1, facing +x (facing=1) or -x.
    axis 'y': plane y=at spanning x a0..a1, facing +y or -y."""
    o = inset * facing
    if axis == 'x':
        x = at + o
        pts = [(x, a0, z0), (x, a1, z0), (x, a1, z1), (x, a0, z1)] if facing > 0 else [(x, a1, z0), (x, a0, z0), (x, a0, z1), (x, a1, z1)]
    else:
        y = at + o
        pts = [(a1, y, z0), (a0, y, z0), (a0, y, z1), (a1, y, z1)] if facing > 0 else [(a0, y, z0), (a1, y, z0), (a1, y, z1), (a0, y, z1)]
    bm = bmesh.new(); bm.faces.new([bm.verts.new(p) for p in pts])
    _emit_fixed_uv(bm, m, [(0, 0), (1, 0), (1, 1), (0, 1)])


def _emit_fixed_uv(bm, m, uvs):
    M = _frame[-1]; bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    kind = m.get('k', 'std'); zn = _zone[-1] + _suffix(kind)
    zo = Z(zn); base = len(zo.V); mi = zo.mat_index(m)
    zo.V.extend(tuple(v.co) for v in bm.verts)
    for f in bm.faces:
        zo.F.append(tuple(base + v.index for v in f.verts)); zo.FM.append(mi); zo.UV.extend(uvs)
    bm.free()


# ---------------------------------------------------------------- imported models (Poly Haven, CC0)
PLANTS = ('plant', 'shrub', 'fern', 'anthurium', 'calathea', 'pachira', 'sorrel')
def is_plant(name): return any(k in name for k in PLANTS)


MODELS = []
MODEL_MATS = {}


def model(name, x, y, z, height=None, width=None, rot=0., scale=None, max_faces=None, variant=0):
    """Import assets_src/models/<name>/*.gltf, sit it on (x, y, z) in the current frame, scaled to a height or width."""
    path = next((SRC / 'models' / name).glob('*.gltf'))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    objs = [o for o in new if o.type == 'MESH']
    for o in objs:                                   # bake parent transforms into the mesh, drop empties
        o.data = o.data.copy(); o.data.transform(o.matrix_world); o.parent = None; o.matrix_world = Matrix.Identity(4)
    for o in new:
        if o.type != 'MESH': bpy.data.objects.remove(o)
    # Some assets hold several variants side by side (plants especially). Group objects whose footprints overlap
    # and keep one group (variant index, counted from the group nearest the file origin).
    boxes = []
    for o in objs:
        xs = [v.co.x for v in o.data.vertices]; ys = [v.co.y for v in o.data.vertices]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    grp = list(range(len(objs)))
    def root(i):
        while grp[i] != i: grp[i] = grp[grp[i]]; i = grp[i]
        return i
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = boxes[i], boxes[j]
            if a[0] - .01 <= b[2] and b[0] - .01 <= a[2] and a[1] - .01 <= b[3] and b[1] - .01 <= a[3]: grp[root(i)] = root(j)
    clusters = {}
    for i in range(len(objs)): clusters.setdefault(root(i), []).append(i)
    if len(clusters) > 1:
        def dist(c):
            xs = [boxes[i][0] for i in c] + [boxes[i][2] for i in c]; ys = [boxes[i][1] for i in c] + [boxes[i][3] for i in c]
            return ((min(xs) + max(xs)) / 2) ** 2 + ((min(ys) + max(ys)) / 2) ** 2
        order = sorted(clusters.values(), key=dist)
        keep = set(order[variant % len(order)])
        for i, o in enumerate(objs):
            if i not in keep: bpy.data.objects.remove(o)
        objs = [o for i, o in enumerate(objs) if i in keep]
    # phone budget: decimate heavy scans. Plants are decimated gently (never below 30 %) or their leaves tear.
    plant = is_plant(name)
    budget = max_faces or (18000 if plant else 4000)
    total = sum(len(o.data.polygons) for o in objs)
    if total > budget:
        for o in objs:
            bpy.context.view_layer.objects.active = o
            d = o.modifiers.new('dec', 'DECIMATE'); d.ratio = max(.3 if plant else .02, budget / total)
            bpy.ops.object.modifier_apply(modifier='dec')
    pts = [v.co for o in objs for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    s = scale or (height / (hi.z - lo.z) if height else width / max(hi.x - lo.x, hi.y - lo.y) if width else 1)
    c = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    M = _frame[-1] @ Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(rot), 4, 'Z') @ Matrix.Scale(s, 4) @ Matrix.Translation(-c)
    for o in objs:
        o.data.transform(M); o.matrix_world = Matrix.Identity(4)
        o['zone'] = _zone[-1]; o.name = f'{"plt" if plant else "mdl"}_{name}'
        for ms in o.material_slots:
            # every import of the same asset brings copies (name.001, .002): reuse the first, so primitives merge
            if ms.material:
                base = re.sub(r'\.\d{3}$', '', ms.material.name)
                first = MODEL_MATS.setdefault(base, ms.material)
                if first is not ms.material: ms.material = first
            mm = ms.material
            if mm and 'k' not in mm:
                mm['k'] = 'cut' if mm.blend_method in ('CLIP', 'HASHED', 'BLEND') or any(l.to_socket.name == 'Alpha' for l in mm.node_tree.links) else 'std'
                img = next((n.image for n in mm.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and any(l.from_node == n and l.to_socket.name in ('Base Color', 'A', 'Color1') for l in mm.node_tree.links)), None)
                if img:
                    web = f'{name}_{Path(img.filepath).name}'; IMAGES[web] = Path(bpy.path.abspath(img.filepath)); mm['tex'] = web
                p = mm.node_tree.nodes.get('Principled BSDF')
                mm['tint'] = '#FFFFFF'; mm['gloss'] = 0.
                if p and not img:
                    c3 = p.inputs['Base Color'].default_value
                    srgb = [(1.055 * c ** (1 / 2.4) - .055) if c > .0031308 else c * 12.92 for c in c3[:3]]
                    mm['tint'] = '#' + ''.join(f'{int(max(0, min(1, v)) * 255):02X}' for v in srgb)
    MODELS.extend(objs)
    return objs


# ---------------------------------------------------------------- navigation data for the viewer
LAYOUT = {'levels': [], 'walk': [], 'block': [], 'ramps': [], 'spots': [], 'probes': [], 'seats': []}


def level(name, z):
    LAYOUT['levels'].append({'name': name, 'z': z}); return len(LAYOUT['levels']) - 1


def _rect_world(x0, y0, x1, y1):
    M = _frame[-1]; pts = [M @ Vector((x, y, 0)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return [round(min(p.x for p in pts), 3), round(min(p.y for p in pts), 3), round(max(p.x for p in pts), 3), round(max(p.y for p in pts), 3)]


def walk(lv, x0, y0, x1, y1): LAYOUT['walk'].append([lv, *_rect_world(x0, y0, x1, y1)])
def blockrect(lv, x0, y0, x1, y1): LAYOUT['block'].append([lv, *_rect_world(x0, y0, x1, y1)])


def ramp(x0, y0, x1, y1, axis, z0, z1, lv0, lv1):
    """A stair flight the visitor can walk: height goes z0 -> z1 along +axis ('x'/'y') or -axis ('-x'/'-y')."""
    LAYOUT['ramps'].append({'r': _rect_world(x0, y0, x1, y1), 'axis': axis, 'z0': z0, 'z1': z1, 'lv0': lv0, 'lv1': lv1})


def spot(name, lv, x, y, look_x, look_y, look_z=None, start=False):
    LAYOUT['spots'].append({'name': name, 'lv': lv, 'x': x, 'y': y, 'lx': look_x, 'ly': look_y, 'lz': look_z, 'start': start})


def seat(name, lv, x=0., y=0., h=.45, face=(0, 1)):
    """A place to sit (one per area): local point and facing in the current furniture frame; h = seat height."""
    M = _frame[-1]; p = M @ Vector((x, y, 0)); d = (M.to_3x3() @ Vector((face[0], face[1], 0))).normalized()
    LAYOUT['seats'].append({'name': name, 'lv': lv, 'x': round(p.x, 3), 'y': round(p.y, 3), 'z': round(p.z, 3), 'h': h,
                            'fx': round(d.x, 3), 'fy': round(d.y, 3)})


def probe(name, lv, x0, y0, z0, x1, y1, z1, at=None):
    """Reflection probe box (the room it covers) and where the cube camera sits."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    LAYOUT['probes'].append({'name': name, 'lv': lv, 'box': [x0, y0, z0, x1, y1, z1], 'at': at or [cx, cy, z0 + 1.4]})


# ---------------------------------------------------------------- finish
def finish(sc, extra=None):
    coll = sc.collection
    for name, zo in ZONES.items():
        if not zo.F: continue
        me = bpy.data.meshes.new(name)
        me.from_pydata(zo.V, [], zo.F)
        uv = me.uv_layers.new(name='UVMap'); flat = [c for uvp in zo.UV for c in uvp]
        uv.data.foreach_set('uv', flat)
        for m in zo.mats: me.materials.append(m)
        me.polygons.foreach_set('material_index', zo.FM)
        me.validate(); me.update()
        o = bpy.data.objects.new(f'zone_{name}', me); coll.objects.link(o); o['zone'] = name
    LAYOUT['images'] = {k: str(v) for k, v in IMAGES.items()}
    if extra: LAYOUT.update(extra)
    json.dump(LAYOUT, open(OUT / 'layout.json', 'w'), indent=1)
    print('ZONES', {k: len(v.F) for k, v in ZONES.items()}, 'MODELS', len(MODELS), 'MATS', len(_mats))
