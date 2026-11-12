"""Bake lighting per zone and export the web assets.

Run:  blender -b build/villa.blend -P blender/bake.py -- [--quick] [--zones gf,ff] [--spp 256]
For each zone (ext, gf, ff, sf):
  1. join the zone mesh with the props placed in it,
  2. add a second UV map 'Light' (smart project + pack),
  3. bake Cycles DIFFUSE light (direct + indirect, no colour) into a float image; glass and water are hidden
     so daylight passes through windows, lamps and LED strips stay on,
  4. denoise (OIDN through the compositor) -> build/light_<zone>.npy (float16),
  5. export web/assets/zones/<zone>.glb (geometry, both UV maps, material extras; no images) and the zone's
     fx/glass objects (no lightmap) alongside.
Then run tools/post.py (plain Python) to encode the lightmaps, copy textures and make the sky.
"""
import sys, json, time, shutil, math
from pathlib import Path
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from lib import gpu, ROOT, OUT

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
QUICK = '--quick' in argv
ZONES = opt('--zones', 'ext,site,gf,ff,sf').split(',')
SPP = int(opt('--spp', 24 if QUICK else 384))
RES = {'ext': 1024, 'site': 512, 'gf': 1024, 'ff': 1024, 'sf': 1024} if QUICK else {'ext': 4096, 'site': 1024, 'gf': 4096, 'ff': 4096, 'sf': 4096}
MODEL_SCALE = .35        # props get (0.35)^2 of the texel density of architecture
TRIM_SCALE = 2.5         # thin trims (frames, skirting, handles, metal) get 2.5^2 the density: no blotches
TRIM_MATS = {'walnutTrim', 'brass', 'chrome', 'bronze', 'blackMetal', 'alu', 'liftFrame'}
WEB = ROOT / 'web' / 'assets'
for d in ('zones', 'light', 'tex'): (WEB / d).mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene; gpu()
t0 = time.time()
log = lambda *a: print(f'[{time.time() - t0:7.1f}s]', *a, flush=True)
layout = json.load(open(OUT / 'layout.json'))


def objs_of(zone, suffix=''):
    name = f'zone_{zone}{suffix}'
    out = [o for o in sc.objects if o.name == name]
    return out


def join(objs, name):
    for ob in objs:                                   # remember which faces are props (smaller lightmap islands)
        a = ob.data.attributes.get('mdl') or ob.data.attributes.new('mdl', 'INT', 'FACE')
        a.data.foreach_set('value', [1 if ob.name.startswith('mdl_') else 0] * len(ob.data.polygons))
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1: bpy.ops.object.join()
    o = bpy.context.object; o.name = name; o.data.name = name
    # keep only UVMap (first) so glTF TEXCOORD_0 = tiling UVs, TEXCOORD_1 = lightmap
    for uv in list(o.data.uv_layers)[1:]:
        if uv.name != 'UVMap': o.data.uv_layers.remove(uv)
    if o.data.uv_layers and o.data.uv_layers[0].name != 'UVMap': o.data.uv_layers[0].name = 'UVMap'
    return o


def light_uv(o):
    me = o.data
    uv = me.uv_layers.new(name='Light'); me.uv_layers.active = uv
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.003, area_weight=0., correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    mdl = np.zeros(len(me.polygons), np.int32); me.attributes['mdl'].data.foreach_get('value', mdl)
    uv = me.uv_layers['Light']                       # re-fetch: the handle goes stale across edit-mode switches
    n = len(uv.data); co = np.empty(n * 2, np.float32); uv.data.foreach_get('uv', co); co = co.reshape(-1, 2)
    ls = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_start', ls)
    lt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', lt)
    mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('material_index', mi)
    trim_idx = {i for i, m in enumerate(me.materials) if m and m.name.split('.')[0] in TRIM_MATS}
    scale = np.ones(n, np.float32)                    # per-loop island scale (scaling about the origin; packing moves islands)
    for s0, t, f, m in zip(ls, lt, mdl, mi):
        if f: scale[s0:s0 + t] = MODEL_SCALE
        elif m in trim_idx: scale[s0:s0 + t] = TRIM_SCALE
    co *= scale[:, None]; uv.data.foreach_set('uv', co.ravel())
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(margin=.002, rotate=True, shape_method='AABB', scale=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    me.uv_layers.active = me.uv_layers['UVMap']; uv.active_render = False


def bake_light(o, size, kind='DIFFUSE', light=True, spp=None, tag='L'):
    """kind DIFFUSE + light: irradiance (direct + indirect). DIFFUSE + not light: albedo. NORMAL: world normals."""
    im = bpy.data.images.new(f'{tag}_{o.name}', size, size, float_buffer=True); im.colorspace_settings.name = 'Non-Color'
    added = []
    for m in o.data.materials:
        if m is None: continue
        nt = m.node_tree
        uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'Light'
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = im; nt.links.new(uvn.outputs['UV'], n.inputs['Vector'])
        for x in nt.nodes: x.select = False
        n.select = True; nt.nodes.active = n; added.append((nt, n, uvn))
    sc.cycles.samples = spp or SPP; sc.cycles.use_denoising = False
    b = sc.render.bake; b.use_pass_direct, b.use_pass_indirect, b.use_pass_color = light, light, not light
    b.normal_space = 'OBJECT'
    b.margin = 8 if QUICK else 16; b.use_clear = True; b.target = 'IMAGE_TEXTURES'
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    uvs = o.data.uv_layers; uvs.active = uvs['Light']        # bake writes pixels through the ACTIVE uv map
    bpy.ops.object.bake(type=kind)
    uvs.active = uvs['UVMap']
    for nt, n, uvn in added: nt.nodes.remove(n); nt.nodes.remove(uvn)
    return im


def guides(o, size):
    """Albedo and normal guide images (in lightmap space) so OIDN keeps edges and texture boundaries crisp."""
    alb = bake_light(o, size, 'DIFFUSE', light=False, spp=4, tag='A')
    nor = bake_light(o, size, 'NORMAL', spp=4, tag='N')
    px = np.empty(size * size * 4, np.float32); nor.pixels.foreach_get(px); px = px.reshape(-1, 4)
    px[:, :3] = px[:, :3] * 2 - 1; nor.pixels.foreach_set(px.ravel())        # 0..1 encoding -> -1..1 for OIDN
    return alb, nor


def denoise(im, alb=None, nor=None):
    """OIDN via the compositor (with albedo + normal guides when given); the Composite result is written to an EXR
    and read back (the Viewer node stays empty in background mode). Falls back to the raw bake."""
    try:
        sc.use_nodes = True; tree = sc.node_tree; tree.nodes.clear()
        a = tree.nodes.new('CompositorNodeImage'); a.image = im
        d = tree.nodes.new('CompositorNodeDenoise'); d.use_hdr = True
        if hasattr(d, 'prefilter'): d.prefilter = 'ACCURATE'
        c = tree.nodes.new('CompositorNodeComposite')
        tree.links.new(a.outputs[0], d.inputs['Image']); tree.links.new(d.outputs[0], c.inputs[0])
        for img, sock in ((alb, 'Albedo'), (nor, 'Normal')):
            if img is not None:
                g = tree.nodes.new('CompositorNodeImage'); g.image = img; tree.links.new(g.outputs[0], d.inputs[sock])
        eng = sc.render.engine; sc.render.engine = 'BLENDER_WORKBENCH'
        sc.render.resolution_x, sc.render.resolution_y = im.size; sc.render.resolution_percentage = 100
        st = sc.render.image_settings; st.file_format = 'OPEN_EXR'; st.color_depth = '32'
        exr = OUT / f'_dn_{im.name}.exr'; sc.render.filepath = str(exr)
        hidden = [ob for ob in sc.objects if not ob.hide_render]
        for ob in hidden: ob.hide_render = True
        bpy.ops.render.render(write_still=True)
        for ob in hidden: ob.hide_render = False
        sc.render.engine = eng; sc.use_nodes = False
        vi = bpy.data.images.load(str(exr))
        px = np.empty(vi.size[0] * vi.size[1] * 4, np.float32); vi.pixels.foreach_get(px)
        out = px.reshape(vi.size[1], vi.size[0], 4)[..., :3]
        bpy.data.images.remove(vi); exr.unlink()
        if out.shape[:2] == (im.size[1], im.size[0]) and np.isfinite(out).all() and out.max() > 0:
            log('  denoised'); return out
        log('  denoise output unusable, using raw')
    except Exception as e:
        log('  denoise failed:', e)
    px = np.empty(im.size[0] * im.size[1] * 4, np.float32); im.pixels.foreach_get(px)
    return px.reshape(im.size[1], im.size[0], 4)[..., :3]


def export(objs, path, draco=True, attributes=False):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    extra = {'export_attributes': True, 'export_vertex_color': 'NONE'} if attributes else {}
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True, export_image_format='NONE', **extra,
                              export_extras=True, export_apply=True, export_lights=False, export_cameras=False,
                              export_texcoords=True, export_normals=True, export_materials='EXPORT', export_yup=True,
                              export_draco_mesh_compression_enable=draco and not QUICK, export_draco_mesh_compression_level=6,
                              export_draco_position_quantization=14, export_draco_normal_quantization=10,
                              export_draco_texcoord_quantization=14, export_draco_generic_quantization=12)


MOODS = opt('--moods', 'day,night').split(',')
SUN = next((o for o in sc.objects if o.type == 'LIGHT' and o.data.type == 'SUN'), None)
BG = sc.world.node_tree.nodes['Background']; BG_DAY = BG.inputs['Strength'].default_value


def set_mood(mood):
    """day: sun + sky + lamps. night (dusk): no sun, a faint blue sky, every lamp, cove and facade light on."""
    night = mood == 'night'
    if SUN: SUN.hide_render = night
    BG.inputs['Strength'].default_value = .045 if night else BG_DAY


def bake_plants(zone):
    """Plants: light baked into per-vertex colours (one float attribute per mood, _LDAY / _LNIGHT). Thin leaves
    bake badly into a lightmap; per-vertex light keeps soft shading and occlusion on every leaf."""
    plants = [o for o in sc.objects if o.name.startswith(('plt_', 'mdl_')) and o.get('zone') == zone]     # plants + props
    if not plants: return None
    bpy.ops.object.select_all(action='DESELECT')
    for p in plants: p.select_set(True)
    bpy.context.view_layer.objects.active = plants[0]
    if len(plants) > 1: bpy.ops.object.join()
    o = bpy.context.object; o.name = f'plants_{zone}'; me = o.data
    for uv in list(me.uv_layers)[1:]: me.uv_layers.remove(uv)
    if me.uv_layers: me.uv_layers[0].name = 'UVMap'
    for mood in MOODS:
        set_mood(mood)
        name = '_L' + mood.upper()
        a = me.color_attributes.get(name) or me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
        me.color_attributes.active_color = a
        sc.cycles.samples = 32 if QUICK else max(256, SPP * 2)
        b = sc.render.bake; b.use_pass_direct, b.use_pass_indirect, b.use_pass_color = True, True, False; b.target = 'VERTEX_COLORS'
        bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
        bpy.ops.object.bake(type='DIFFUSE')
        b.target = 'IMAGE_TEXTURES'
        # one smoothing pass over neighbours softens per-vertex sampling noise
        n = len(me.vertices); col = np.empty(n * 4, np.float32); a.data.foreach_get('color', col); col = col.reshape(n, 4)
        ev = np.empty(len(me.edges) * 2, np.int32); me.edges.foreach_get('vertices', ev); ev = ev.reshape(-1, 2)
        acc = col.copy(); cnt = np.ones(n, np.float32)
        np.add.at(acc, ev[:, 0], col[ev[:, 1]]); np.add.at(acc, ev[:, 1], col[ev[:, 0]])
        np.add.at(cnt, ev[:, 0], 1); np.add.at(cnt, ev[:, 1], 1)
        col = .5 * col + .5 * acc / cnt[:, None]; col[:, 3] = 1
        a.data.foreach_set('color', col.ravel())
        log('  plants baked', mood, n, 'vertices')
    set_mood('day')
    export([o], WEB / 'zones' / f'{zone}_plants.glb', draco=False, attributes=True)
    return f'zones/{zone}_plants.glb'


# ---------------------------------------------------------------- run
manifest = {'zones': {}, 'layout': 'layout.json'}
if (WEB / 'scene.json').exists():
    manifest = json.load(open(WEB / 'scene.json')); manifest.setdefault('zones', {})
for m in bpy.data.materials:                             # metals have no diffuse response: bake their light as if matte
    p = m.node_tree.nodes.get('Principled BSDF') if m.use_nodes and m.node_tree else None
    if p: p.inputs['Metallic'].default_value = 0.
glass = [o for o in sc.objects if o.name.endswith('_glass')]
for o in glass: o.hide_render = True                     # daylight through windows and over water
for zone in ZONES:
    objs = objs_of(zone)
    if not objs: continue
    log('zone', zone, len(objs), 'objects')
    o = join(objs, f'bake_{zone}')
    light_uv(o); log('  uv ready,', len(o.data.polygons), 'faces')
    alb, nor = guides(o, RES[zone]); log('  guides baked')
    for mood in MOODS:
        set_mood(mood)
        im = bake_light(o, RES[zone]); log('  baked', mood, RES[zone], SPP, 'spp')
        arr = denoise(im, alb, nor)
        np.save(OUT / f'light_{zone}{"" if mood == "day" else "_" + mood}.npy', arr.astype(np.float16)); log('  lightmap saved (npy)')
        bpy.data.images.remove(im)
    set_mood('day'); bpy.data.images.remove(alb); bpy.data.images.remove(nor)
    export([o], WEB / 'zones' / f'{zone}.glb')
    fx = objs_of(zone, '_fx') + objs_of(zone, '_glass')
    if fx: export(fx, WEB / 'zones' / f'{zone}_fx.glb')
    pl = bake_plants(zone)
    manifest['zones'][zone] = {'glb': f'zones/{zone}.glb', 'fx': f'zones/{zone}_fx.glb' if fx else None, 'light': f'light/{zone}.jpg',
                               'moods': MOODS, 'plants': pl}
    log('  exported')

manifest['sun'] = layout.get('sun'); manifest['quick'] = QUICK
json.dump(manifest, open(WEB / 'scene.json', 'w'), indent=1)
log('done', ZONES)
